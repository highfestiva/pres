#!/usr/bin/env python3
'''A simple text editor, trying to immitate the eminating Notepad++.'''


import curses
import json
import os
import string


# MSYS translation table
msys_keys = {
  'KEY_B1':     'KEY_LEFT',
  'KEY_B3':     'KEY_RIGHT',
  'KEY_A2':     'KEY_UP',
  'KEY_C2':     'KEY_DOWN',
  'CTL_PAD4':   'kLFT5',
  'CTL_PAD6':   'kRIT5',
  'CTL_LEFT':   'kLFT5',
  'CTL_RIGHT':  'kRIT5',
  'KEY_A3':     'KEY_PPAGE',
  'KEY_C3':     'KEY_NPAGE',
  'KEY_A1':     'KEY_HOME',
  'KEY_C1':     'KEY_END',
  'CTL_PAD7':   'kHOM5',
  'CTL_PAD1':   'kEND5',
  'CTL_HOME':   'kHOM5',
  'CTL_END':    'kEND5',
  'CTL_PAD8':   'kUP5',
  'CTL_PAD2':   'kDN5',
  '\x08':       'KEY_BACKSPACE',
  'PADSTOP':    'KEY_DC',
}

ext2syntax = {
  'py':       { 'keyword': {'for','if','def','True','False','None'}, 'comment': {'#'}, 'block_start': {"'''",'"""'}, 'block_end': {"'''",'"""'}, 'string': {'"',"'"} },
  'default':  { 'keyword': {} }
}

str_whitespace = ' \t'
str_number = string.digits + '._'
str_letter = string.ascii_letters + '_'
str_letter2 = str_letter + string.digits
str_printable = string.punctuation

colors = [curses.COLOR_WHITE, curses.COLOR_BLUE, curses.COLOR_RED, curses.COLOR_GREEN, curses.COLOR_GREEN]
bgcol = curses.COLOR_BLACK


xlatkey = lambda k: msys_keys.get(k, k)
portable_erase = lambda scr: scr.clear() if os.name=='nt' else scr.erase()


def read_conf_raw():
  try:
    fn = os.path.expanduser('~/.pres/config')
    return json.load(open(fn, 'rt'))
  except:
    return {}


def write_conf_raw(conf):
  d = os.path.expanduser('~/.pres')
  try: os.mkdir(d)
  except: pass
  fn = d + '/config'
  json.dump(conf, open(fn, 'wt'), indent=2)


def read_conf(section, key):
  conf = read_conf_raw()
  section = conf.get(section, {})
  return section.get(key)


def write_conf(section, key, value):
  conf = read_conf_raw()
  if section not in conf:
    conf[section] = {}
  conf[section][key] = value
  write_conf_raw(conf)


def fn2syntax(fn):
  ext = os.path.splitext(fn)[1][1:]
  return ext2syntax.get(ext, ext2syntax['default'])


def token_color(t):
  if t in 'KO':
    return 2
  elif t in 'DS':
    return 3
  elif t in 'CB':
    return 4
  return 1


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


class SyntaxState:
  def __init__(self, ss=None):
    self.in_block = False if ss is None else ss.in_block
    self.new_line()

  def new_line(self):
    self.in_string = False
    self.in_comment = False


class Tokenizer:
  def __init__(self, syntax):
    self.syntax = syntax

  def tokenize(self, line):
    self.tokens = []
    token = Token()
    i = 0
    for i,ch in enumerate(line):
      if ch in str_whitespace:
        self._close(token, i)
      elif token.t=='D' and ch in str_number:
        self._add(token, i, ch, 'D')
      elif token.t=='A' and ch in str_letter2:
        self._add(token, i, ch, 'A')
      elif ch in str_letter:
        self._add(token, i, ch, 'A')
      elif ch in string.digits:
        self._add(token, i, ch, 'D')
      elif ch in str_printable:
        self._add(token, i, ch, 'O')
      else:
        self._close(token, i)
    self._close(token, i)
    return self.tokens

  def syntax_parse(self, lines):
    if not self.syntax:
      return
    self.line_state = []
    ss = SyntaxState()
    syntax_lines = []
    for line in lines:
      ss.new_line()
      self.line_state.append(ss)
      syntax_tokens = self.syntax_parse_line(len(self.line_state)-1, line)
      ss = SyntaxState(ss)
      syntax_lines.append(syntax_tokens)
    return syntax_lines

  def syntax_parse_line(self, idx, line):
    ss = self.line_state[idx]
    syntax_line = []
    for token in line:
      if ss.in_block:
        if token.t == 'O' and token.s in self.syntax['block_end']:
          ss.in_block = False
        token.t = 'B'
      elif ss.in_string:
        if token.t == 'O' and token.s in self.syntax['string']:
          ss.in_string = False
        token.t = 'S'
      elif ss.in_comment:
        token.t = 'C'
      elif token.t == 'O':
        if token.s in self.syntax['block_start']:
          ss.in_block = True
          token.t = 'B'
        elif token.s in self.syntax['string']:
          ss.in_string = True
          token.t = 'S'
        elif token.s in self.syntax['comment']:
          ss.in_comment = True
          token.t = 'C'
      syntax_line.append(token)
    return syntax_line

  def is_block(self, token):
    return token.s in self.syntax['block_start'] or token.s in self.syntax['block_end']

  def _close(self, token, i):
    if token.t:
      token.x1 = i
      if token.t == 'A' and token.s in self.syntax['keyword']:
        token.t = 'K'
      self.tokens.append(Token(token))
      token.clear()

  def _add(self, token, i, ch, t):
    if token.t == t == 'O' and token.s.endswith(ch) and ch not in '(){}[]':
      token.x1 = i+1
      token.s += ch
    elif token.t != t or t == 'O':
      self._close(token, i)
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
    self.tokenizer = Tokenizer(self.syntax)

  def hilite_all(self, lines):
    self.token_lines = []
    for line in lines:
      token_line = self.tokenizer.tokenize(line)
      self.token_lines.append(token_line)
    self.syntax_lines = self.tokenizer.syntax_parse(self.token_lines)
    self._colorize_lines(self.syntax_lines)

  def hilite_line(self, y, lines):
    token_line = self.tokenizer.tokenize(lines[y])
    if len([1 for t in self.token_lines[y] if self.tokenizer.is_block(t)]) == len([1 for t in token_line if self.tokenizer.is_block(t)]):
      self.token_lines[y] = token_line
      self.syntax_lines[y] = self.tokenizer.syntax_parse_line(y, token_line)
      self._colorize_lines([self.syntax_lines[y]])
    else:
      self.hilite_all(lines)

  def _colorize_lines(self, syntax_lines):
    # set color
    for token_line in syntax_lines:
      for token in token_line:
        token.col = token_color(token.t)


class Editor:
  def __init__(self, file=None, syntax=None):
    self.file = file
    self.hiliter = Hilighter(syntax)
    self.lines = ['']
    self.x = 0
    self.y = 0
    self.cx = 0 # cursor xy
    self.cy = 0
    self.editable = True
    self.quit = False

  def load_state(self):
    path = os.path.abspath(self.file.name)
    conf = read_conf('files', path)
    if conf:
      self.cy = min(len(self.lines)-1, conf.get('cy', 0))
      self.cx = min(len(self.lines[self.cy]), conf.get('cx', 0))

  def save_state(self):
    if self.lines != ['']:
      path = os.path.abspath(self.file.name)
      write_conf('files', path, {'cy':self.cy, 'cx':self.cx})

  def show(self):
    self.load()
    self.hiliter.hilite_all(self.lines)
    self.load_state()
    curses.wrapper(self.run)

  def load(self):
    if self.file is not None:
      txt = self.file.read()
      self.lines = txt.splitlines()
      if txt.endswith('\n'):
        self.lines.append('')

  def run(self, scr):
    maxy, maxx = scr.getmaxyx()
    self.x = max(0, self.cx-maxx//2)
    self.y = max(0, self.cy-maxy//2)
    for i,col in enumerate(colors, 1):
      curses.init_pair(i, col, bgcol)
    while not self.quit:
      self.display(scr)
      try:
        k = xlatkey(scr.getkey())
        self.handle_key(scr, k)
      except KeyboardInterrupt:
        pass

  def display(self, scr):
    portable_erase(scr)
    maxy, maxx = scr.getmaxyx()
    syntax_lines = self.hiliter.syntax_lines[self.y:self.y+maxy]
    
    # truncate cursor to end of line
    linelen = len(self.lines[self.cy])
    cx = min(self.cx, linelen)
    if cx < self.x:
      self.x = max(0, cx-2)
    scx = max(0, cx - self.x)

    for sy, token_line in enumerate(syntax_lines):
      for token in token_line:
        x0 = max(0, self.x-token.x0)
        x1 = max(0, min(len(token.s), self.x+maxx-token.x0))
        s = token.s[x0:x1]
        if s:
          try:
            sx = max(0, token.x0-self.x)
            scr.addstr(sy, sx, s, curses.color_pair(token.col))
          except:
            print('error:', token, token.x0, self.x, sx, s)
            exit(1)
    scr.move(self.cy - self.y, scx)
    scr.refresh()
  
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
      self.hiliter.hilite_line(self.cy, self.lines)
    elif self.editable and k == 'KEY_BACKSPACE':
      if self.cx > 0:
        self.lines[self.cy] = line[:self.cx-1] + line[self.cx:]
        self.cx -= 1
        if self.cx-self.x < lowest_x:
          self.scroll_rows(scr, -2)
      self.hiliter.hilite_line(self.cy, self.lines)
    elif self.editable and k == 'KEY_DC':
      self.lines[self.cy] = line[:self.cx] + line[self.cx+1:]
      self.hiliter.hilite_line(self.cy, self.lines)
    elif k in '\x18': # Ctrl+X
      self.quit = True
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
  for editor in editors:
    editor.save_state()


if __name__ == '__main__':
  main()
