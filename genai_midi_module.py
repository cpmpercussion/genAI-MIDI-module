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
import click
from websockets.sync.client import connect # websockets connection

click.secho("Opening configuration.", fg="yellow")
with open("config.toml", "rb") as f:
    config = tomllib.load(f)

click.secho("Listing MIDI Inputs and Outputs", fg='yellow')
click.secho(f"Input: {mido.get_input_names()}", fg = 'blue')
click.secho(f"Output: {mido.get_output_names()}", fg = 'blue')


def match_midi_port_to_list(port, port_list):
    """Return the closest actual MIDI port name given a partial match and a list."""
    if port in port_list:
        return port
    contains_list = [x for x in port_list if port in x]
    if not contains_list:
        return False
    else:
        return contains_list[0]


try:
    click.secho("Opening MIDI port for input/output.", fg='yellow')
    desired_input_port = match_midi_port_to_list(config["midi"]["in_device"], mido.get_input_names())
    midi_in_port = mido.open_input(desired_input_port)
    desired_output_port = match_midi_port_to_list(config["midi"]["out_device"], mido.get_output_names())
    midi_out_port = mido.open_output(desired_output_port)
    click.secho(f"MIDI: in port is: {midi_in_port.name}", fg='green')
    click.secho(f"MIDI: out port is: {midi_out_port.name}", fg='green')
except: 
    midi_in_port = None
    midi_out_port = None
    click.secho("Could not open MIDI input or output (or just one of those).", fg='red')

try:
    click.secho("Opening Serial Port for MIDI in/out.", fg='yellow')
    ser = serial.Serial('/dev/ttyAMA0', baudrate=31250)
except:
    ser = None
    click.secho("Could not open serial port, might be in development mode.", fg='red')

# Set up websocket client
if config["websocket"]:
    click.secho("Opening websocket for OSC in/out.", fg='yellow')
    client_url = f"ws://{config['websocket']['client_ip']}:{config['websocket']['client_port']}" # the URL for the websocket client to send to.
    try:
        websocket = connect(client_url)
        click.secho(f"Success! WS Connected to {config['websocket']['client_ip']}", fg='green')
    except:
        click.secho("Could not connect to websocket.", fg='red')
        websocket = None

# Input and output to serial are bytes (0-255)
# Output to Pd is a float (0-1)
parser = argparse.ArgumentParser(description='Predictive Musical Interaction MDRNN Interface.')
parser.add_argument('-l', '--log', dest='logging', action="store_true", help='Save input and RNN data to a log file.')
parser.add_argument('-v', '--verbose', dest='verbose', action="store_true", help='Verbose mode, print prediction results.')
args = parser.parse_args()

# Import Keras and tensorflow, doing this later to make CLI more responsive.
click.secho("Importing MDRNN.", fg='yellow')
start_import = time.time()
import empi_mdrnn
import tensorflow.compat.v1 as tf
print("Done. That took", time.time() - start_import, "seconds.")

# Choose model parameters.
if config["model"]["size"] == 'xs':
    click.secho("Using XS model.")
    mdrnn_units = 32
    mdrnn_mixes = 5
    mdrnn_layers = 2
elif config["model"]["size"] == 's':
    click.secho("Using S model.")
    mdrnn_units = 64
    mdrnn_mixes = 5
    mdrnn_layers = 2
elif config["model"]["size"] == 'm':
    click.secho("Using M model.")
    mdrnn_units = 128
    mdrnn_mixes = 5
    mdrnn_layers = 2
elif config["model"]["size"] == 'l':
    click.secho("Using L model.")
    mdrnn_units = 256
    mdrnn_mixes = 5
    mdrnn_layers = 2
elif config["model"]["size"] == 'xl':
    click.secho("Using XL model.")
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
    click.secho(f'out: {values}', fg='green')

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
        serial_send_midi(midi_msg)
        websocket_send_midi(midi_msg)
        # do this by whatever other channels necessary
    except KeyError:
        pass

    # play the present note
    midi_msg = mido.Message('note_on', channel=channel, note=pitch, velocity=velocity)
    midi_out_port.send(midi_msg)
    serial_send_midi(midi_msg)
    websocket_send_midi(midi_msg)
    last_midi_notes[channel] = pitch

def send_midi_note_offs():
    """Sends note offs on any MIDI channels that have been used for notes."""
    global last_midi_notes
    outconf = config["midi"]["output"]
    out_channels = [x[1] for x in outconf if x[0] == "note_on"]
    for i in out_channels:
        try:
            midi_msg = mido.Message('note_off', channel=i-1, note=last_midi_notes[i-1], velocity=0)
            midi_out_port.send(midi_msg)
            serial_send_midi(midi_msg)
            websocket_send_midi(midi_msg)
        except KeyError:
            pass


def send_control_change(channel, control, value):
    """Send a MIDI control change message"""
    midi_msg = mido.Message('control_change', channel=channel, control=control, value=value)
    midi_out_port.send(midi_msg)
    serial_send_midi(midi_msg)
    websocket_send_midi(midi_msg)


def serial_send_midi(message):
    """Sends a mido MIDI message via the very basic serial output on Raspberry Pi GPIO."""
    try:
        ser.write(message.bin)
    except: 
        pass


def websocket_send_midi(message):
    """Sends a mido MIDI message via websockets if available."""
    # global websocket
    if message.type == "note_on":
        ws_msg = f"/channel/{message.channel}/noteon/{message.note}/{message.velocity}"
    if message.type == "note_off":
        ws_msg = f"/channel/{message.channel}/noteoff/{message.note}/{message.velocity}"
    if message.type == "control_change":
        ws_msg = f"/channel/{message.channel}/cc/{message.control}/{message.value}"
    else:
        return

    try: 
        websocket.send(ws_msg) # websocket message
    except:
        pass

def playback_rnn_loop():
    # Plays back RNN notes from its buffer queue.
    while True:
        item = rnn_output_buffer.get(block=True, timeout=None)  # Blocks until next item is available.
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
    values = list(map(int, (np.ceil(int_input * 127))))
    click.secho(f"in: {values}", fg='yellow')
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
        if message.type == "note_on":
            try:
                index = config["midi"]["input"].index(["note_on", message.channel+1])
                value = message.note / 127.0
                construct_input_list(index,value)
            except ValueError:
                pass

        if message.type == "control_change":
            try:
                index = config["midi"]["input"].index(["control_change", message.channel+1, message.control])
                value = message.value / 127.0
                construct_input_list(index,value)
            except ValueError:
                pass


def handle_websocket_input():
    """Handle websocket input messages that might arrive"""
    if websocket is None:
        return
    for message in websocket:
        m = message.split('/')
        chan = m[1]
        note = m[3]
        vel = m[4]
        if m[2] == "noteon":
            # note_on
            try:
                index = config["midi"]["input"].index(["note_on", chan+1])
                value = note / 127.0
                construct_input_list(index,value)  
            except ValueError:
                pass
          
        # if m[2] == "noteoff":
        #     # note_off - do nothing
        if m[2] == "cc":
            # cc
            try:
                index = config["midi"]["input"].index(["control_change", chan+1, note])
                value = vel / 127.0
                construct_input_list(index,value)
            except ValueError:
                pass
        # global websocket
        # ws_msg = f"/channel/{message.channel}/noteon/{message.note}/{message.velocity}"
        # ws_msg = f"/channel/{message.channel}/noteoff/{message.note}/{message.velocity}"
        # ws_msg = f"/channel/{message.channel}/cc/{message.control}/{message.value}"


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
            click.secho("switching to response.", bg='red', fg='black')
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
            click.secho("switching to call.", bg='blue', fg='black')
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
    click.secho(f'Logging enabled: {LOG_FILE}', fg='yellow')
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
click.secho("Preparing MDRNN.", fg='yellow')
tf.keras.backend.set_session(sess)
with compute_graph.as_default():
    if config["model"]["file"] != "":
        net.load_model(model_file=config["model"]["file"]) # load custom model.
    else:
        net.load_model()  # try loading from default file location.

click.secho("Preparing MDRNN thread.", fg='yellow')
rnn_thread = Thread(target=playback_rnn_loop, name="rnn_player_thread", daemon=True)

try:
    rnn_thread.start()
    click.secho("RNN Thread Started", fg="green")
    while True:
        make_prediction(sess, compute_graph)
        if config["interaction"]["mode"] == "callresponse":
            handle_midi_input() # handles incoming midi queue
            # handle_websocket_input() # handles incoming websocket queue
            monitor_user_action()
except KeyboardInterrupt:
    click.secho("\nCtrl-C received... exiting.", fg='red')
    thread_running = False
    rnn_thread.join(timeout=0.1)
    send_midi_note_offs() # stop all midi notes.
    try:
        websocket.close()
    except:
        pass
finally:
    click.secho("\nDone, shutting down.", fg='red')
