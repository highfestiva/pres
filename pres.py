#!/usr/bin/env python3

import curses
import os


# MSYS translation table
msys_keys = {
  'KEY_B1':   'KEY_LEFT',
  'KEY_B3':   'KEY_RIGHT',
  'KEY_A2':   'KEY_UP',
  'KEY_C2':   'KEY_DOWN',
  'CTL_PAD4': 'kLFT5',
  'CTL_PAD6': 'kRIT5',
  'KEY_A3':   'KEY_PPAGE',
  'KEY_C3':   'KEY_NPAGE',
  'KEY_A1':   'KEY_HOME',
  'KEY_C1':   'KEY_END',
  'CTL_PAD7': 'kHOM5',
  'CTL_PAD1': 'kEND5',
  'CTL_PAD8': 'kUP5',
  'CTL_PAD2': 'kDN5',
  '\x08':     'KEY_BACKSPACE',
  'PADSTOP':  'KEY_DC',
}

ext2syntax = {
  'py': { 'keyword': {'for','if','def','True','False','None'}, 'comment': {'#'}, 'block_start': {"'''",'"""'}, 'block_end': {"'''",'"""'}, 'string': {'"',"'"} },
}

whitespace = ' \t'


xlatkey = lambda k: msys_keys.get(k, k)


class Token:
  def __init__(self, copy=None):
    if copy is None:
      self.clear()
    else:
      self.x0 = copy.x0
      self.x1 = copy.x1
      self.s = copy.s
      self.t = copy.t

  def clear(self):
    self.x0 = 0
    self.x1 = 0
    self.s = ''
    self.t = ''

  def __repr__(self):
    return f'{self.s}[{self.t}]'


class Tokenizer:
  def __init__(self, syntax):
    self.syntax = syntax

  def tokenize(self, line):
    self.tokens = []
    token = Token()
    i = 0
    for i,ch in enumerate(line):
      if ch in whitespace:
        self.close(token, i)
      elif token.t=='D' and (ch.isdigit() or ch in '._'):
        self.add(token, i, ch, 'D')
      elif token.t=='A' and (ch.isalnum() or ch == '_'):
        self.add(token, i, ch, 'A')
      elif ch.isalpha():
        self.add(token, i, ch, 'A')
      elif ch.isdigit():
        self.add(token, i, ch, 'D')
      elif ch.isprintable():
        self.add(token, i, ch, 'O')
      else:
        self.close(token, i)
    self.close(token, i)
    return self.tokens

  def close(self, token, i):
    if token.t:
      token.x1 = i
      if token.t == 'A' and self.syntax:
        if token.s in self.syntax['keyword']:
          token.t = 'K'
      self.tokens.append(Token(token))
      token.clear()

  def add(self, token, i, ch, t):
    if token.t != t:
      self.close(token, i)
      token.x0 = i
      token.x1 = i+1
      token.s = ch
      token.t = t
    else:
      token.x1 = i+1
      token.s += ch


class Hilighter:
  def __init__(self, syntax):
    self.syntax = syntax

  def run(self, lines):
    token_lines = []
    tokenizer = Tokenizer(self.syntax)
    for line in lines:
      token_line = tokenizer.tokenize(line)
      for token in token_line:
        token.col = self.token_col(token.t)
      token_lines.append(token_line)
    return token_lines

  def token_col(self, t):
    if t in 'KO':
      return 2
    elif t in 'D':
      return 3
    return 1


def fn2syntax(fn):
  ext = os.path.splitext(fn)[1][1:]
  return ext2syntax.get(ext)


class Editor:
  def __init__(self, file=None, syntax=None):
    self.file = file
    self.syntax = syntax
    self.lines = ['']
    self.x = 0
    self.y = 0
    self.cx = 0 # cursor xy
    self.cy = 0
    self.editable = True

  def show(self):
    self.load()
    curses.wrapper(self.run)

  def load(self):
    if self.file is not None:
      txt = self.file.read()
      self.lines = txt.splitlines()
      if txt.endswith('\n'):
        self.lines.append('')

  def run(self, scr):
    try:
      curses.init_pair(1, curses.COLOR_WHITE, curses.COLOR_BLACK)
      curses.init_pair(2, curses.COLOR_BLUE, curses.COLOR_BLACK)
      curses.init_pair(3, curses.COLOR_RED, curses.COLOR_BLACK)
      while True:
        self.display(scr)
        k = xlatkey(scr.getkey())
        self.handle_key(scr, k)
    except KeyboardInterrupt:
      pass

  def display(self, scr):
    scr.clear()
    maxy, maxx = scr.getmaxyx()
    h = Hilighter(self.syntax)
    token_lines = h.run(self.lines[max(0, self.y-10): self.y+maxy-1])
    token_lines = token_lines[-maxy+1:]
    for sy, token_line in enumerate(token_lines):
      for token in token_line:
        x0 = max(0, self.x-token.x0)
        x1 = max(0, min(len(token.s), self.x+maxx-token.x0))
        s = token.s[x0:x1]
        if s:
          scr.addstr(sy, token.x0-self.x, s, curses.color_pair(token.col))
    # truncate cursor to end of line
    linelen = len(self.lines[self.cy])
    cx = min(self.cx, linelen)
    x = max(0, cx - self.x)
    scr.refresh()
    scr.move(self.cy - self.y, x)
  
  def handle_key(self, scr, k):
    maxy, maxx = scr.getmaxyx()
    lowest_y = len(self.lines) - maxy + 1
    lowest_x = 2
    highest_x = maxx - 2
    line = self.lines[self.cy]
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
    elif k == 'kLFT5': # Ctrl+Left
      i = 1
      for i,ch in enumerate(line[self.cx-i::-1], i):
        if ch.isalnum() or ch == '_':
          break
      for i,ch in enumerate(line[self.cx-i::-1], i):
        if not ch.isalnum() and ch != '_':
          break
      i -= 1
      self.cx = max(0, min(len(line), self.cx-i))
      if self.cx <= self.x+1:
        self.scroll_rows(scr, -i)
    elif k == 'kRIT5': # Ctrl+Right
      i = 0
      for i,ch in enumerate(line[self.cx+i:], i):
        if not ch.isalnum() and ch != '_':
          break
      for i,ch in enumerate(line[self.cx+i:], i):
        if ch.isalnum() or ch == '_':
          break
      self.cx = max(0, min(len(line), self.cx+i))
      if self.cx == self.x+maxx-1:
        self.scroll_rows(scr, +i)
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
    elif self.editable and k.isprintable() and len(k) == 1:
      self.lines[self.cy] = line[:self.cx] + k + line[self.cx:]
      self.cx += 1
      if self.cx-self.x > highest_x:
        self.scroll_rows(scr, +2)
    elif self.editable and k == 'KEY_BACKSPACE':
      if self.cx > 0:
        self.lines[self.cy] = line[:self.cx-1] + line[self.cx:]
        self.cx -= 1
        if self.cx-self.x < lowest_x:
          self.scroll_rows(scr, -2)
    elif self.editable and k == 'KEY_DC':
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
  parser.add_argument('files', nargs='*', help='files to open')
  options = parser.parse_args()

  if False: # for sys.stdin...
    try:
      f = open('/dev/tty')
      os.dup2(f.fileno(), 0)
    except FileNotFoundError:
      pass # possibly Windows

  editors = []
  for fn in options.files:
    editors.append(Editor(open(fn), fn2syntax(fn)))
  if not editors:
    editors = [Editor()]
  editors[0].show()


if __name__ == '__main__':
  main()
