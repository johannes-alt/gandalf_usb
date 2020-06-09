# -----------------------------------------------------------------------------
# Copyright (c) 2009-2016 Nicolas P. Rougier. All rights reserved.
# Distributed under the (new) BSD License.
# -----------------------------------------------------------------------------

# http://www.labri.fr/perso/nrougier/python-opengl/#about-this-book
# https://github.com/glumpy/glumpy/blob/master/examples/collection-update.py
import sys, signal
import numpy as np
from glumpy import app, collections

from threading import Thread, Lock
sys.path.append(".")
sys.path.append("./gandalf_usb")
import decode, reader

vertex = """
// Externs
// ------------------------------------
// extern vec3  position;
// extern float id;
// extern vec4  color;
// ... user-defined through collection init dtypes
// -----------------------------------------------
uniform float rows, cols;
varying float v_x;
varying vec4 v_color;
void main()
{
    // This line is mandatory and is responsible for fetching uniforms
    // from the underlying uniform texture
    fetch_uniforms();
    // color can end up being an attribute or a varying
    // If you want to make sure to pass it to the fragment,
    // It's better to define it here explicitly
    if (selected > 0.0)
        v_color = vec4(1,1,1,1*id);
    else
        v_color = vec4(color.rgb, color.a*id);
    float index = collection_index;
    // Compute row/col from collection_index
    float col = mod(index,cols) + 0.5;
    float row = floor(index/cols) + 0.5;
    float x = -1.0 + col * (2.0/cols);
    float y = -1.0 + row * (2.0/rows);
    float width = 0.95 / (1.0*cols);
    float height = 0.95 / (1.0*rows);
    v_x = xscale*position.x;
    gl_Position = vec4(x + width*v_x, y + height*position.y, 0.0, 1.0);
}
"""

fragment = """
// Collection varyings are not propagated to the fragment shader
// -------------------------------------------------------------
varying float v_x;
varying vec4 v_color;
void main(void)
{
    if( v_x < -0.95) discard;
    if( v_x > +0.95) discard;
    gl_FragColor = v_color;
}
"""

rows,cols = 4, 4
n, p = rows*cols, 100
lines = collections.RawPathCollection(
    user_dtype = [("selected",  (np.float32, 1), 'shared', 0),
                  ("xscale",    (np.float32, 1), 'shared', 1)],
    color="shared", vertex=vertex, fragment=fragment)
lines.append(np.tile(.2-1, (n*p, 3)), itemsize=p)

lines["rows"] = rows
lines["cols"] = cols
lines["color"][:n] = np.random.uniform(0.5, 1.0, (n, 4))
lines["color"][:n, 3] = 1.0 # set alpha to 1.0
#lines["selected"] = 0.0
#lines["xscale"] = 1.0 #[:n] = np.random.uniform(1., 25., n)

# Each segment has two extra points for breaking the line strip
positions = lines["position"].reshape(rows*cols,p+2, 3)
positions[:, 1:-1, 0] = np.tile(np.linspace(-1, +1, p), n).reshape(rows*cols, p)

# Here we ensure:
#   * first point = second point
#   * last point = prev last point
positions[:, 0] = positions[:, 1]
positions[:, -1] = positions[:, -2]


lock = Lock()
events = [None]*16

window = app.Window(1400,1000)
@window.event
def on_draw(dt):
    window.clear()
    lines.draw()

    # wait for the next time it is possible to read from the events dict
    lock.acquire(True)
    for i in range(16):
        ev = events[i]
        if ev is not None:
            if ev.biterr: print('!! biterr !!')
            positions[:,:min(len(ev.samples), p), 1][ev.ch] = np.array(ev.samples[:min(len(ev.samples), p)])/1000. - 1.
        events[i] = None
    lock.release()

def get_index(x,y):
    """ Find the index of the plot under mouse """
    y = window.height-y
    col = int(x/float(window.width)*cols) % cols
    row = int(y/float(window.height)*rows) % rows
    return row*cols + col

@window.event
def on_mouse_motion(x,y,dx,dy):
    index = get_index(x,y)
    lines["selected"] = 0
    lines["selected"][index] = 1

@window.event
def on_mouse_scroll(x, y, dx, dy):
    index = get_index(x,y)
    dx = -np.sign(dy) * .05
    lines["xscale"][index] *= np.exp(2.5*dx)
    lines["xscale"][index] = min(max(1.0, lines["xscale"][index]), 100.)


def f():
    for ev in decode.events(reader.netcat_source('10.4.73.183', 12345)):
        # for ev in decode.events(reader.file_source('/tmp/data0')):
        if exitFlag: break
        lock.acquire(True)
        events[ev.ch] = ev
        lock.release()

def exit(signum, frame):
    global exitFlag
    exitFlag = 1

signal.signal(signal.SIGINT, exit)
signal.signal(signal.SIGTERM, exit)

exitFlag = 0
t = Thread(target=f)
t.start()
app.run()
exitFlag = 1
t.join()
