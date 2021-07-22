#!/usr/bin/env python3

import argparse
from collections import OrderedDict
from enum import Enum
import json
import os
import sys
import time
import traceback

"""
Example json config
{
  "operators": {
    "doggo": {
    },
    "speargal": {
    },
    "mastermei": {
    },
    "ke": {
    },
    "neng": {
    },
    "fragrant": {
    },
    "migrru": {
    },
    "ola": {
    },
    "masterla": {
    },
    "laser": {
    },
    "snow": {
    },
    "z2": {
    },
    "sheep": {
    },
    "lumberjack": {
      "consume": true
    },
    "block": {
      "consume": true,
      "no_dir": true
    },
    "hplane": {
      "consume": true,
      "no_dir": true
    }
  },
  "grids": {
    "dumpling_6x10": {
      "width": 2160,
      "height": 1080,
      "max_panel_width": 172,
      "row_edges": [176,264,372,485,613,754,892],
      "num_columns": 10,
      "topleft_x": 462,
      "topright_x": 1704,
      "bottomleft_x": 276,
      "bottomright_x": 1888,
      "pause_x": 2047,
      "pause_y": 97,
      "speed_x": 1875,
      "speed_y": 105,
      "activate_x": 1394,
      "activate_y": 653,
      "retreat_x": 1026,
      "retreat_y": 385
    }
  }
}

Example keyboard record input

# This is a comment.
# First command must be "use"!
# use name,name:init_num
use doggo,mastermei,hplane:0
# Second command must be "grid"!
grid dumpling_6x10
# The above two lines are mandatory

# Press enter always toggle pause.

setn hplane 1 # now 1 hplane ready to deploy!
d hplane 3 5 u # use 1 hplane on row 3 col 5
t # toggle speed
d doggo 4 6 d # deploy doggo
r doggo # retreat doggo
d mastermei 3 2 r # deploy mastermei
t # toggle speed
a mastermei # active mastermei's skill
x mastermei # mastermei down!
q # quit
"""

def log(msg):
  print("# {}".format(msg))

class Adb:

  @staticmethod
  def _do(cmd):
    print(cmd)
    os.system(cmd)

  @staticmethod
  def connect(host, port):
    Adb._do('adb connect {}:{}'.format(host, port))

  @staticmethod
  def tap(x, y):
    Adb._do('adb shell input tap {} {}'.format(int(x), int(y)))

  @staticmethod
  def drag(from_x, from_y, to_x, to_y, duration_ms=800):
    Adb._do('adb shell input draganddrop {} {} {} {} {}'
            .format(int(from_x), int(from_y), int(to_x), int(to_y), int(duration_ms)))

  @staticmethod
  def swipe(from_x, from_y, to_x, to_y, duration_ms=800):
    Adb._do('adb shell input swipe {} {} {} {} {}'
            .format(int(from_x), int(from_y), int(to_x), int(to_y), int(duration_ms)))


class GameMap:
  def __init__(self, grid):
    self.grid = grid

  def _column_frac(self, a, b, n):
    unit = (b - a) * 1.0 / self.grid['num_columns']
    return a + unit * (n + 0.5)

  def _row_frac(self, a, b, n):
    row_edges = self.grid['row_edges']
    L = row_edges[-1] - row_edges[0]
    l = row_edges[n] - row_edges[0]
    l += (row_edges[n+1] - row_edges[n]) * 0.5
    return (a * (L - l) + b * l) / L

  def grid_to_coordinates(self, row, col):
    tx = self._column_frac(self.grid['topleft_x'], self.grid['topright_x'], col)
    bx = self._column_frac(self.grid['bottomleft_x'], self.grid['bottomright_x'], col)
    x = self._row_frac(tx, bx, row)
    y = self._row_frac(self.grid['row_edges'][0], self.grid['row_edges'][-1], row)
    print(row, col)
    print(tx, bx, x, y)
    return int(x), int(y)

  def panel_to_coordinates(self, idx, available):
    max_panel_width = self.grid['max_panel_width']
    panel_width = max_panel_width
    screen_width = self.grid['width']
    if max_panel_width * available > screen_width:
      panel_width = screen_width * 1.0 / available
    x = screen_width - (available - idx - 0.5) * panel_width
    y = self.grid['height'] - panel_width * 0.5
    print(idx, available)
    return int(x), int(y)

class Level:
  class State(Enum):
    INIT = 1
    USE = 2
    GRID = 3
    PLAY = 4

  def __init__(self, config):
    self.config = config
    self.state = Level.State.INIT

    self.grid = None
    self.operators_in_use = OrderedDict()

    self.start_time_ms = None
    self.paused = True
    self.last_pause_time_ms = None
    self.paused_duration_ms = 0

  def loop(self, input_path, output_path):
    if output_path:
      with open(input_path) as input_fd, open(output_path, 'w') as output_fd:
        self._loop(input_fd, output_fd)
    else:
      with open(input_path) as input_fd:
        self._loop(input_fd, None)

  def _loop(self, input_fd, output_fd):
    # Game is expected to be paused when the script starts.
    # Togther with pausing this should align game time & replay time.
    log("reading input file")

    self.start_time_ms = self._monotonic_now_ms()

    for line in input_fd:
      self._do_line(line.strip(), output_fd, interactive=False)

    assert(self.state is Level.State.PLAY)

    log("end of input file, paused")
    self.toggle_pause()

    log("next command:")
    for line in sys.stdin:
      self._do_line(line.strip(), output_fd, interactive=True)
      log("next command:")

  def _do_line(self, line, output_fd, interactive):
    if not line:
      if interactive and self.state != Level.State.INIT:
        self.toggle_pause()
      return

    if line.startswith('#'):
      return

    if not interactive:
      log("exec: {}".format(line))

    tokens = line.split()
    was_paused = None
    try:
      if tokens[0] == 'use':
        self._do_use_operators(*tokens[1:])
      elif tokens[0] == 'grid':
        self._do_set_grid(*tokens[1:])
      elif tokens[0] == 'setn':
        self._do_set_num(*tokens[1:])
      elif tokens[0] == 't':
        self.toggle_speed()
      elif tokens[0] == 'd' or tokens[0] == 'dep':
        was_paused = self.may_pause()
        self._do_deploy(*tokens[1:])
      elif tokens[0] == 'r' or tokens[0] == 'ret':
        was_paused = self.may_pause()
        self._do_retreat(*tokens[1:])
      elif tokens[0] == 'a' or tokens[0] == 'act':
        was_paused = self.may_pause()
        self._do_activate(*tokens[1:])
      elif tokens[0] == 'x':
        was_paused = self.may_pause()
        self._do_recycle(*tokens[1:])
      elif tokens[0] == 'till':
        self._do_wait_till(*tokens[1:])
      elif tokens[0] == 'q':
        sys.exit(0)
      else:
        log("strange command: {}".format(line))
        return
    except KeyboardInterrupt as e:
      print(e)
      traceback.print_tb(e.__traceback__)
      sys.exit(0)
    except Exception as e:
      print(e)
      traceback.print_tb(e.__traceback__)
      log("error with line: {}".format(line))
      self.may_pause_again(was_paused)
      return

    if output_fd:
      if self.state is Level.State.PLAY and not self.paused:
        diff_ms = self._game_duration_ms()
        output_fd.write('till {}\n'.format(diff_ms))
      output_fd.write(' '.join(tokens) + '\n')
      output_fd.flush()

    self.may_pause_again(was_paused)

    if self.state is Level.State.GRID:
      log("screen config finished, resume")
      self.toggle_pause()
      self.state = Level.State.PLAY

  def _do_use_operators(self, operators_str):
    assert(self.state is Level.State.INIT)
    self.state = Level.State.USE

    for word in operators_str.split(','):
      tokens = word.split(':')
      assert(len(tokens) < 3)
      name = tokens[0]
      operator = dict(self.config["operators"][name])
      if len(tokens) == 1:
        operator['count'] = 1
      else:
        _, num = tokens
        operator['count'] = int(num)
      self.operators_in_use[name] = operator

  def _do_set_grid(self, name):
    assert(self.state is Level.State.USE)
    self.state = Level.State.GRID
    self.grid = self.config['grids'][name]
    self.game_map = GameMap(self.grid)

  def _do_set_num(self, name, count):
    assert(self.state is Level.State.PLAY)
    self.operators_in_use[name]['count'] = int(count)

  def toggle_speed(self):
    Adb.tap(self.grid['speed_x'], self.grid['speed_y'])

  def _do_deploy(self, name, row, col, direction=None):
    operator = self.operators_in_use[name]
    assert(operator['count'] > 0)
    row = int(row) - 1
    col = int(col) - 1
    assert(row >= 0)
    assert(col >= 0)
    assert(row < len(self.grid['row_edges']))
    assert(col < self.grid['num_columns'])
    if direction:
      assert(direction in set(['up', 'down', 'left', 'right', 'u', 'd', 'l', 'r']))
    else:
      assert(operator['no_dir'])
    if not operator.get('consume'):
      assert(operator.get('coordinates') is None)

    idx, available = self._get_operator_panel_index(name)
    panel_x, panel_y = self.game_map.panel_to_coordinates(idx, available)
    grid_x, grid_y = self.game_map.grid_to_coordinates(row, col)
    Adb.tap(panel_x, panel_y)
    Adb.drag(panel_x, panel_y, grid_x, grid_y)
    if direction == 'up' or direction == 'u':
      self.swipe_up(grid_x, grid_y)
    elif direction == 'down' or direction == 'd':
      self.swipe_down(grid_x, grid_y)
    elif direction == 'left' or direction == 'l':
      self.swipe_left(grid_x, grid_y)
    elif direction == 'right' or direction == 'r':
      self.swipe_right(grid_x, grid_y)
    operator["coordinates"] = (grid_x, grid_y)
    operator["count"] -= 1

  def _do_retreat(self, name):
    operator = self.operators_in_use[name]
    assert(not operator.get('consume'))
    assert(operator['count'] == 0)
    coordinates = operator['coordinates']
    assert(coordinates is not None)

    grid_x, grid_y = coordinates
    Adb.tap(grid_x, grid_y)
    Adb.tap(self.grid["retreat_x"], self.grid["retreat_y"])
    operator['coordinates'] = None
    operator['count'] = 1

  def _do_activate(self, name):
    operator = self.operators_in_use[name]
    coordinates = operator['coordinates']
    assert(coordinates is not None)

    grid_x, grid_y = coordinates
    Adb.tap(grid_x, grid_y)
    Adb.tap(self.grid["activate_x"], self.grid["activate_y"])

  def _do_recycle(self, name):
    operator = self.operators_in_use[name]
    assert(not operator.get('consume'))
    assert(operator['count'] == 0)
    assert(operator['coordinates'] is not None)
    operator['coordinates'] = None
    operator['count'] = 1

  def _do_wait_till(self, till_ms):
    assert(self.state is Level.State.PLAY)

    till_ms = int(till_ms)
    now_ms = self._game_duration_ms()
    if now_ms >= till_ms:
      return
    diff_ms = till_ms - now_ms
    while diff_ms > 0:
      sleep_ms = min(diff_ms, 10)
      diff_ms -= sleep_ms
      try:
        time.sleep(sleep_ms * 0.001)
      except e:
        self.toggle_pause()
        raise e

  def toggle_pause(self):
    Adb.tap(self.grid['pause_x'], self.grid['pause_y'])
    if self.paused:
      self.paused = False
      if self.state is Level.State.PLAY:
        self.paused_duration_ms += self._monotonic_now_ms() - self.last_pause_time_ms
      print("# resumed")
    else:
      self.paused = True
      if self.state is Level.State.PLAY:
        self.last_pause_time_ms = self._monotonic_now_ms()
      print("# paused")

  def may_pause(self):
    was_paused = self.paused
    if was_paused:
      self.toggle_pause()
    return was_paused

  def may_pause_again(self, was_paused):
    if was_paused:
      self.toggle_pause()

  def _get_operator_panel_index(self, name):
    available = 0
    idx = 0
    i = 0
    for k, v in self.operators_in_use.items():
      if k == name:
        idx = i
      if v['count'] > 0:
        i += 1
        available += 1
    return idx, available

  @staticmethod
  def _monotonic_now_ms():
    return round(time.monotonic() * 1000)

  def _game_duration_ms(self):
    assert(not self.paused)
    assert(self.state is Level.State.PLAY)
    return self._monotonic_now_ms() - self.start_time_ms - self.paused_duration_ms

  def swipe_up(self, x, y, dist=200, duration_ms=200):
    Adb.swipe(x, y, x, max(0, y - dist), duration_ms)

  def swipe_down(self, x, y, dist=200, duration_ms=200):
    Adb.swipe(x, y, x, min(self.grid['height'], y + dist), duration_ms)

  def swipe_left(self, x, y, dist=200, duration_ms=200):
    Adb.swipe(x, y, max(0, x - dist), y, duration_ms)

  def swipe_right(self, x, y, dist=200, duration_ms=200):
    Adb.swipe(x, y, min(self.grid['width'], x + dist), y, duration_ms)


def main():
  parser = argparse.ArgumentParser(description='Simple record and replay for arknights.')
  parser.add_argument('-c', '--config_path', dest='config_path',
                      required=True, help='json config file path')
  parser.add_argument('-i', '--input_path', dest='input_path',
                      required=True,  help='input command file path')
  parser.add_argument('-o', '--output_path', dest='output_path',
                      help='optional output command file path')
  parser.add_argument('-H', '--adb_host', dest='adb_host',
                      help='adb host', default='127.0.0.1')
  parser.add_argument('-p', '--adb_port', dest='adb_port',
                      help='adb host', default=5555)

  args = parser.parse_args()
  config = None
  with open(args.config_path) as fd:
    config = json.load(fd)
  Adb.connect(args.adb_host, args.adb_port)
  level = Level(config)
  level.loop(args.input_path, args.output_path)


if __name__ == '__main__':
  main()
