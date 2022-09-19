#!/usr/bin/env python3

import curses
import os


class Editor:
  def __init__(self, txt):
    self.lines = txt.splitlines()
    if txt.endswith('\n'):
      self.lines.append('')
    self.x = 0
    self.y = 0
    self.cx = 0 # cursor xy
    self.cy = 0
    self.editable = True
    f = open('/dev/tty')
    os.dup2(f.fileno(), 0)
    curses.wrapper(self.run)

  def run(self, scr):
    try:
      while True:
        self.display(scr)
        self.k = k = scr.getkey()
        self.handle_key(scr, k)
    except KeyboardInterrupt:
      pass

  def display(self, scr):
    scr.erase()
    maxy, maxx = scr.getmaxyx()
    for sy, line in enumerate(self.lines[self.y:self.y+maxy-1]):
      scr.addstr(sy, 0, line[self.x:self.x+maxx])
    # truncate cursor to end of line
    linelen = len(self.lines[self.cy])
    cx = min(self.cx, linelen)
    x = max(0, cx - self.x)
    scr.move(self.cy - self.y, x)
    scr.refresh()
  
  def handle_key(self, scr, k):
    maxy, maxx = scr.getmaxyx()
    lowest_y = len(self.lines) - maxy + 1
    lowest_x = 2
    highest_x = maxx - 2
    if k == 'KEY_PPAGE':
      self.scroll_lines(scr, -maxy, y_cursor=True)
    elif k == 'KEY_NPAGE':
      self.scroll_lines(scr, +maxy, y_cursor=True)
    elif k == 'KEY_UP':
      self.cy = max(0, self.cy-1)
      if self.cy <= self.y+1:
        self.scroll_lines(scr, -1)
    elif k == 'KEY_DOWN':
      self.cy = min(len(self.lines)-1, self.cy+1)
      if self.cy >= self.y+maxy-2:
        self.scroll_lines(scr, +1)
    elif k == 'kUP5': # Ctrl+Up
      self.scroll_lines(scr, -1)
    elif k == 'kDN5': # Ctrl+Down
      self.scroll_lines(scr, +1)
    elif k == 'KEY_LEFT':
      self.cx = max(0, min(len(self.lines[self.cy])-1, self.cx-1))
      if self.cx <= self.x+1:
        self.scroll_rows(scr, -1)
    elif k == 'KEY_RIGHT':
      self.cx = min(len(self.lines[self.cy]), self.cx+1)
      if self.cx >= self.y+highest_x:
        self.scroll_rows(scr, +1)
    elif k == 'KEY_HOME':
      self.x = self.cx = 0
    elif k == 'KEY_END':
      self.cx = len(self.lines[self.cy])
      self.x = max(0, self.cx-highest_x)
    elif k == 'kHOM5':
      self.x = self.cx = self.y = self.cy = 0
    elif k == 'kEND5':
      self.y = lowest_y
      self.cy = len(self.lines) - 1
      self.cx = len(self.lines[self.cy])
      self.x = max(0, self.cx-highest_x)
    elif self.editable and (k == ' ' or k.isalnum()):
      line = self.lines[self.cy]
      self.lines[self.cy] = line[:self.cx] + k + line[self.cx:]
      self.cx += 1
      if self.cx-self.x > highest_x:
        self.scroll_rows(scr, +2)
    elif self.editable and k == 'KEY_BACKSPACE':
      if self.cx > 0:
        line = self.lines[self.cy]
        self.lines[self.cy] = line[:self.cx-1] + line[self.cx:]
        self.cx -= 1
        if self.cx-self.x < lowest_x:
          self.scroll_rows(scr, -2)
    elif self.editable and k == 'KEY_DC':
      line = self.lines[self.cy]
      self.lines[self.cy] = line[:self.cx] + line[self.cx+1:]
    elif k in '\x04\x18': # Ctrl+D or Ctrl+X
      raise KeyboardInterrupt()
    else:
      print('key:', k.encode())

  def scroll_rows(self, scr, dx):
    maxy, maxx = scr.getmaxyx()
    self.x = max(0, self.x+dx)
    return

  def scroll_lines(self, scr, dy, y_cursor=False):
    maxy, maxx = scr.getmaxyx()
    lowest_y = len(self.lines) - maxy + 1
    y = self.y + dy
    if y <= 0:
      if self.y == 0 and y_cursor:
        if self.cy == 0:
          self.cx = 0
        else:
          self.cy = 0
      y = 0
    elif y >= lowest_y:
      if self.y == lowest_y and y_cursor:
        if self.cy == len(self.lines)-1:
          self.cx = len(self.lines[-1])
        else:
          self.cy = len(self.lines)-1
      y = lowest_y

    d = y - self.y
    self.y += d
    if y_cursor:
      self.cy = min(len(self.lines)-1, max(0, self.cy+d))
    self.cy = min(self.y+maxy-1, self.cy)
    self.cy = max(self.y, self.cy)


def main():
  import argparse
  import sys

  parser = argparse.ArgumentParser()
  parser.add_argument('-e', action='store_true', help='refresh editing')
  parser.add_argument('files', nargs='*', type=argparse.FileType('r'), default=[sys.stdin], help='files to present')
  options = parser.parse_args()
  txt = '\n'.join(f.read() for f in options.files)
  Editor(txt)


if __name__ == '__main__':
  main()
