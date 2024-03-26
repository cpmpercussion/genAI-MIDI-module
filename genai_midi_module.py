#!/usr/bin/env python

import logging
import time
import datetime
import numpy as np
import queue
import serial
import argparse
import tomllib
from threading import Thread
import mido
from websockets.sync.client import connect # websockets connection

print("Opening configuration.")
with open("config.toml", "rb") as f:
    config = tomllib.load(f)

print("Listing MIDI Inputs and Outputs")
print("Input:", mido.get_input_names())
print("Output:", mido.get_output_names())
print("By default, mido is going to open the first input and first output ports")

# print("Opening MIDI port for input/output.")
# midi_in_port = mido.open_input(config["midi"]["in_device"])
# midi_out_port = mido.open_output(config["midi"]["out_device"])

try:
    print("Opening MIDI port for input/output.")
    midi_in_port = mido.open_input(config["midi"]["in_device"])
    midi_out_port = mido.open_output(config["midi"]["out_device"])
except: 
    midi_in_port = None
    midi_out_port = None
    print("Could not open MIDI input or output (or just one of those).")

try:
    print("Opening Serial Port for MIDI in/out.")
    ser = serial.Serial('/dev/ttyAMA0', baudrate=31250)
except:
    ser = None
    print("Could not open serial port, might be in development mode.")




print("Configuration: ", config)

# Input and output to serial are bytes (0-255)
# Output to Pd is a float (0-1)
parser = argparse.ArgumentParser(description='Predictive Musical Interaction MDRNN Interface.')
parser.add_argument('-l', '--log', dest='logging', action="store_true", help='Save input and RNN data to a log file.')
parser.add_argument('-v', '--verbose', dest='verbose', action="store_true", help='Verbose mode, print prediction results.')
args = parser.parse_args()

# Import Keras and tensorflow, doing this later to make CLI more responsive.
print("Importing MDRNN.")
start_import = time.time()
import empi_mdrnn
import tensorflow.compat.v1 as tf
print("Done. That took", time.time() - start_import, "seconds.")

# Choose model parameters.
if config["model"]["size"] == 'xs':
    print("Using XS model.")
    mdrnn_units = 32
    mdrnn_mixes = 5
    mdrnn_layers = 2
elif config["model"]["size"] == 's':
    print("Using S model.")
    mdrnn_units = 64
    mdrnn_mixes = 5
    mdrnn_layers = 2
elif config["model"]["size"] == 'm':
    print("Using M model.")
    mdrnn_units = 128
    mdrnn_mixes = 5
    mdrnn_layers = 2
elif config["model"]["size"] == 'l':
    print("Using L model.")
    mdrnn_units = 256
    mdrnn_mixes = 5
    mdrnn_layers = 2
elif config["model"]["size"] == 'xl':
    print("Using XL model.")
    mdrnn_units = 512
    mdrnn_mixes = 5
    mdrnn_layers = 3

dimension = config["model"]["dimension"] # retrieve dimension from the config file.

# Interaction Loop Parameters
# All set to false before setting is chosen.
user_to_rnn = False
rnn_to_rnn = False
rnn_to_sound = False

# Interactive Mapping
if config["interaction"]["mode"] == "callresponse":
    print("Entering call and response mode.")
    # set initial conditions.
    user_to_rnn = True
    rnn_to_rnn = False
    rnn_to_sound = False
elif config["interaction"]["mode"] == "polyphony":
    print("Entering polyphony mode.")
    user_to_rnn = True
    rnn_to_rnn = False
    rnn_to_sound = True
elif config["interaction"]["mode"] == "battle":
    print("Entering battle royale mode.")
    user_to_rnn = False
    rnn_to_rnn = True
    rnn_to_sound = True
elif config["interaction"]["mode"] == "useronly":
    print("Entering user only mode.")
    user_to_rnn = False
    rnn_to_rnn = False
    rnn_to_sound = False


def build_network(sess):
    """Build the MDRNN."""
    empi_mdrnn.MODEL_DIR = "./models/"
    tf.keras.backend.set_session(sess)
    with compute_graph.as_default():
        net = empi_mdrnn.PredictiveMusicMDRNN(mode=empi_mdrnn.NET_MODE_RUN,
                                              dimension=dimension,
                                              n_hidden_units=mdrnn_units,
                                              n_mixtures=mdrnn_mixes,
                                              layers=mdrnn_layers)
        net.pi_temp = config["model"]["pitemp"]
        net.sigma_temp = config["model"]["sigmatemp"]
    print("MDRNN Loaded:", net.model_name())
    return net


def request_rnn_prediction(input_value):
    """ Accesses a single prediction from the RNN. """
    output_value = net.generate_touch(input_value)
    return output_value


def make_prediction(sess, compute_graph):
    # Interaction loop: reads input, makes predictions, outputs results.
    # Make predictions.

    # First deal with user --> MDRNN prediction
    if user_to_rnn and not interface_input_queue.empty():
        item = interface_input_queue.get(block=True, timeout=None)
        tf.keras.backend.set_session(sess)
        with compute_graph.as_default():
            rnn_output = request_rnn_prediction(item)
        if args.verbose:
            print("User->RNN prediction:", rnn_output)
        if rnn_to_sound:
            rnn_output_buffer.put_nowait(rnn_output)
        interface_input_queue.task_done()

    # Now deal with MDRNN --> MDRNN prediction.
    if rnn_to_rnn and rnn_output_buffer.empty() and not rnn_prediction_queue.empty():
        item = rnn_prediction_queue.get(block=True, timeout=None)
        tf.keras.backend.set_session(sess)
        with compute_graph.as_default():
            rnn_output = request_rnn_prediction(item)
        if args.verbose:
            print("RNN->RNN prediction out:", rnn_output)
        rnn_output_buffer.put_nowait(rnn_output)  # put it in the playback queue.
        rnn_prediction_queue.task_done()


last_note_played = []

## The MIDI and websocket sending routines


def send_note_on(channel, pitch, velocity):
    global websocket
    """Send a note on message to the serial output"""
    try:
        ser.write(bytearray([(9 << 4) | channel, pitch, velocity]))
    except: 
        pass
    try:
        websocket.send(f"/channel/{channel}/noteon/{pitch}/{velocity}") # websocket message
    except:
        pass
    try:
        midi_msg = mido.Message('note_on', channel=channel, note=pitch, velocity=velocity)
        midi_out_port.send(midi_msg)
    except:
        pass

def send_note_off(channel, pitch, velocity):
    global websocket
    """Send a note off message to the serial output"""
    try:
        ser.write(bytearray([(8 << 4) | channel, pitch, velocity])) # stop last note
    except:
        pass
    try: 
        websocket.send(f"/channel/{channel}/noteoff/{pitch}/{velocity}") # websocket message
    except:
        pass
    try:
        midi_msg = mido.Message('note_off', channel=channel, note=pitch, velocity=velocity)
        midi_out_port.send(midi_msg)
    except:
        pass

# /channel/1/noteon/54 + ip address + timestamp
# /channel/1/noteoff/54 + ip address + timestamp


# def send_sound_command(command_args):
#     """Send a sound command back to the interface/synth"""
#     global last_note_played
#     assert len(command_args)+1 == dimension, "Dimension not same as prediction size." # Todo more useful error.
#     assert dimension <= 17, "Dimension > 17 is not compatible with MIDI pitch sending."
#     if len(last_note_played) < (dimension-1):
#         # prime the last_note_played list.
#         last_note_played = [0] * (dimension-1)
#     # TODO put in serial sending code here
#     # should just send "note on" based on first argument.
#     new_notes = list(map(int, (np.ceil(command_args * 127))))
#     ## order is (cmd/channel), pitch, vel
#     for channel in range(dimension-1):
#         send_note_off(channel, last_note_played[channel], 0) # stop last note
#         send_note_on(channel, new_notes[channel], 127) # play new note
#     print(f'sent MIDI note: {new_notes}')
#     last_note_played = new_notes # remember last note played


def send_sound_command_midi(command_args):
    """Sends sound commands via MIDI"""
    assert len(command_args)+1 == dimension, "Dimension not same as prediction size." # Todo more useful error.
    outconf = config["midi"]["output"]
    values = list(map(int, (np.ceil(command_args * 127))))
    print(f'sending MIDI note: {values}')

    for i in range(dimension-1):
        if outconf[i][0] == "note_on":
            send_midi_note_on(outconf[i][1]-1, values[i], 127) # note decremented channel (0-15)
        if outconf[i][0] == "control_change":
            send_control_change(outconf[i][1]-1, outconf[i][2], values[i]) # note decrement channel (0-15)
    # TODO: is it a good idea to have all this indexing? easy to screw up.
            

last_midi_notes = {} # dict to store last played notes via midi

def send_midi_note_on(channel, pitch, velocity):
    """Send a MIDI note on (and implicitly handle note_off)"""
    global last_midi_notes
    # stop the previous note
    try:
        midi_msg = mido.Message('note_off', channel=channel, note=last_midi_notes[channel], velocity=0)
        midi_out_port.send(midi_msg)
        # do this by whatever other channels necessary
    except KeyError:
        pass

    # play the present note
    midi_msg = mido.Message('note_on', channel=channel, note=pitch, velocity=velocity)
    midi_out_port.send(midi_msg)
    last_midi_notes[channel] = pitch
    # do this by whatever other channels necessary
    # TODO add cheap serial MIDI
    # TODO add websockets
    # TODO add local OSC?

def send_midi_note_offs():
    global last_midi_notes
    outconf = config["midi"]["output"]
    out_channels = [x[1] for x in outconf if x[0] == "note_on"]
    print("Sending note offs for channels:", out_channels)
    for i in out_channels:
        try:
            midi_msg = mido.Message('note_off', channel=i-1, note=last_midi_notes[i-1], velocity=0)
            midi_out_port.send(midi_msg)
        except KeyError:
            pass


def send_control_change(channel, control, value):
    """Send a MIDI control change message"""
    midi_msg = mido.Message('control_change', channel=channel, control=control, value=value)
    midi_out_port.send(midi_msg)
    # TODO add cheap serial MIDI
    # TODO add websockets
    # TODO add local OSC?


def playback_rnn_loop():
    # Plays back RNN notes from its buffer queue.
    while True:
        item = rnn_output_buffer.get(block=True, timeout=None)  # Blocks until next item is available.
        # print("processing an rnn command", time.time())
        dt = item[0]
        x_pred = np.minimum(np.maximum(item[1:], 0), 1)
        dt = max(dt, 0.001)  # stop accidental minus and zero dt.
        dt = dt * config["model"]["timescale"] # timescale modification!
        time.sleep(dt)  # wait until time to play the sound
        # put last played in queue for prediction.
        rnn_prediction_queue.put_nowait(np.concatenate([np.array([dt]), x_pred]))
        if rnn_to_sound:
            # send_sound_command(x_pred)
            send_sound_command_midi(x_pred)
            # print("RNN Played:", x_pred, "at", dt)
            logging.info("{1},rnn,{0}".format(','.join(map(str, x_pred)),
                         datetime.datetime.now().isoformat()))
        rnn_output_buffer.task_done()


def construct_input_list(index, value):
    """constructs a dense input list from a sparse format (e.g., when receiving MIDI)
    """
    global last_user_interaction_time
    global last_user_interaction_data
    # set up dense interaction list
    int_input = last_user_interaction_data[1:]
    int_input[index] = value
    # log
    print("INPUT:", int_input)
    if args.verbose:
        print("User:", time.time(), ','.join(map(str, int_input)))
    logging.info("{1},interface,{0}".format(','.join(map(str, int_input)),
                 datetime.datetime.now().isoformat()))
    # put it in the queue
    dt = time.time() - last_user_interaction_time
    last_user_interaction_time = time.time()
    last_user_interaction_data = np.array([dt, *int_input])
    assert len(last_user_interaction_data) == dimension, "Input is incorrect dimension, set dimension to %r" % len(last_user_interaction_data)
    # These values are accessed by the RNN in the interaction loop function.
    interface_input_queue.put_nowait(last_user_interaction_data)


def handle_midi_input():
    """Handle MIDI input messages that might come from mido"""
    # TODO add some kind of error checking on reading the midi port here.
    for message in midi_in_port.iter_pending():
        # input_mapping = config["midi"]["input"]
        # print("MIDI-in:", message)

        if message.type == "note_on":
            try:
                index = config["midi"]["input"].index(["note_on", message.channel+1])
            except ValueError:
                return
            value = message.note / 127.0
            # print("Sending note to inputs:", index, value)
            construct_input_list(index,value)
            return
        if message.type == "control_change":
            try:
                index = config["midi"]["input"].index(["control_change", message.channel+1, message.control])
            except ValueError:
                return
            value = message.value / 127.0
            # print("Sending control to inputs:", index, value)
            construct_input_list(index,value)
            return


def monitor_user_action():
    # Handles changing responsibility in Call-Response mode.
    global call_response_mode
    global user_to_rnn
    global rnn_to_rnn
    global rnn_to_sound
    # Check when the last user interaction was
    dt = time.time() - last_user_interaction_time
    if dt > config["interaction"]["threshold"]:
        # switch to response modes.
        user_to_rnn = False
        rnn_to_rnn = True
        rnn_to_sound = True
        if call_response_mode == 'call':
            print("switching to response.")
            call_response_mode = 'response'
            while not rnn_prediction_queue.empty():
                # Make sure there's no inputs waiting to be predicted.
                rnn_prediction_queue.get()
                rnn_prediction_queue.task_done()
            rnn_prediction_queue.put_nowait(last_user_interaction_data)  # prime the RNN queue
    else:
        # switch to call mode.
        user_to_rnn = True
        rnn_to_rnn = False
        rnn_to_sound = False
        if call_response_mode == 'response':
            print("switching to call.")
            call_response_mode = 'call'
            # Empty the RNN queues.
            while not rnn_output_buffer.empty():
                # Make sure there's no actions waiting to be synthesised.
                rnn_output_buffer.get()
                rnn_output_buffer.task_done()
            # close sound control over MIDI
            send_midi_note_offs()




# Logging
LOG_FILE = datetime.datetime.now().isoformat().replace(":", "-")[:19] + "-" + str(dimension) + "d" +  "-mdrnn.log"  # Log file name.
LOG_FILE = "logs/" + LOG_FILE
LOG_FORMAT = '%(message)s'

if args.logging:
    logging.basicConfig(filename=LOG_FILE,
                        level=logging.INFO,
                        format=LOG_FORMAT)
    print("Logging enabled:", LOG_FILE)
# Details for OSC output
INPUT_MESSAGE_ADDRESS = "/interface"
OUTPUT_MESSAGE_ADDRESS = "/prediction"

# Set up runtime variables.
# ## Load the Model
compute_graph = tf.Graph()
with compute_graph.as_default():
    sess = tf.Session()
net = build_network(sess)
interface_input_queue = queue.Queue()
rnn_prediction_queue = queue.Queue()
rnn_output_buffer = queue.Queue()
writing_queue = queue.Queue()
last_user_interaction_time = time.time()
last_user_interaction_data = empi_mdrnn.random_sample(out_dim=dimension)
rnn_prediction_queue.put_nowait(empi_mdrnn.random_sample(out_dim=dimension))
call_response_mode = 'call'

thread_running = True  # todo is this line needed?

# Set up run loop.
print("Preparing MDRNN.")
tf.keras.backend.set_session(sess)
with compute_graph.as_default():
    if config["model"]["file"] != "":
        net.load_model(model_file=config["model"]["file"]) # load custom model.
    else:
        net.load_model()  # try loading from default file location.
print("Preparting MDRNN thread.")

# Set up websocket client
if config["websocket"]:
    client_url = f"ws://{config['websocket']['client_ip']}:{config['websocket']['client_port']}" # the URL for the websocket client to send to.
    try:
        websocket = connect(client_url)
    except:
        print("Could not connect to websocket.")


rnn_thread = Thread(target=playback_rnn_loop, name="rnn_player_thread", daemon=True)

try:
    rnn_thread.start()
    while True:
        make_prediction(sess, compute_graph)
        if config["interaction"]["mode"] == "callresponse":
            handle_midi_input() # handles incoming midi queue
            monitor_user_action()
except KeyboardInterrupt:
    print("\nCtrl-C received... exiting.")
    thread_running = False
    rnn_thread.join(timeout=0.1)
    try: 
        ser.write(bytearray([(8 << 4) | 0, last_note_played, 0])) # stop last note on channel 0 in case.
    except:
        pass
    send_midi_note_offs() # stop all midi notes.
    try:
        websocket.close()
    except:
        pass
finally:
    print("\nDone, shutting down.")
