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
  'CTL_UP':     'kUP5',
  'CTL_DOWN':   'kDN5',
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

COL_BG,COL_KEYW,COL_COMMENT,COL_OP,COL_NUM,COL_STR,COL_BLOCK,COL_TXT,COL_CNT = range(9)
colors = {
  COL_BG:       [   0,    0,    0],
  COL_TXT:      [1000, 1000, 1000],
  COL_KEYW:     [ 300,  500, 1000],
  COL_OP:       [ 300,  800, 1000],
  COL_NUM:      [1000,  400,  500],
  COL_STR:      [ 700,  700,  700],
  COL_COMMENT:  [ 300, 1000,  400],
  COL_BLOCK:    [1000,  600,  200],
}
default_colors = {}
bgcol = COL_BG
token2color = {
  'K': COL_KEYW,
  'O': COL_OP,
  'N': COL_NUM,
  'S': COL_STR,
  'C': COL_COMMENT,
  'B': COL_BLOCK,
}


xlatkey = lambda k: msys_keys.get(k, k)
portable_erase = lambda scr: scr.clear() if os.name=='nt' else scr.erase()
is_txt = lambda ch: ch.isalnum() or ch == '_'
not_txt = lambda ch: not is_txt(ch)
debug_strs = []


def debug(*args):
  s = ' '.join(str(a) for a in args)
  debug_strs.append(s)


class Point:
  def __init__(self, y, x):
    self.x = x
    self.y = y


class Rect:
  def __init__(self, y, x, h, w):
    self.x = x
    self.y = y
    self.w = w
    self.h = h

  def contain(self, point):
    if point.y < self.y:
      self.y = point.y
    elif point.y > self.y+self.h-1:
      self.y = point.y-self.h+1
    if point.x < self.x:
      self.x = point.x
    elif point.x > self.x+self.w-1:
      self.x = point.x-self.w+1

  def truncate(self, point):
    if self.y > point.y:
      point.y = self.y
    elif self.y+self.h-1 < point.y:
      point.y = self.y+self.h-1
    if self.x > point.x:
      point.x = self.x
    elif self.x+self.w-1 < point.x:
      point.x = self.x+self.w-1
    return point
      

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
      elif token.t=='N' and ch in str_number:
        self._add(token, i, ch, 'N')
      elif token.t=='A' and ch in str_letter2:
        self._add(token, i, ch, 'A')
      elif ch in str_letter:
        self._add(token, i, ch, 'A')
      elif ch in string.digits:
        self._add(token, i, ch, 'N')
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
      self.line_state.append(ss)
      syntax_tokens = self.syntax_parse_line(len(self.line_state)-1, line)
      ss = SyntaxState(ss)
      syntax_lines.append(syntax_tokens)
    return syntax_lines

  def syntax_parse_line(self, idx, line):
    ss = self.line_state[idx]
    ss.new_line()
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
        token.col = token2color.get(token.t, COL_TXT)


class Editor:
  def __init__(self, file=None, syntax=None):
    self.file = file
    self.hiliter = Hilighter(syntax)
    self.lines = ['']
    self.x = 0
    self.y = 0
    self.cx = 0 # cursor xy
    self.cy = 0
    self.vcx = 0 # virtual cursor x, temporary holding x when pgup/dn
    self.editable = True
    self.quit = False

  def load_state(self):
    path = os.path.abspath(self.file.name)
    conf = read_conf('files', path)
    if conf:
      self.cx = conf.get('cx', 0)
      self.cy = conf.get('cy', 0)

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
    self.store_colors()
    self.scr = scr

    maxy, maxx = self.scr.getmaxyx()
    # center view around loaded cursor
    dx = self.cx-maxx//2
    dy = self.cy-maxy//2
    self.move_delta_yx(0, 0, dy, dx)

    for col,(r,g,b) in colors.items():
      curses.init_color(col, r, g, b)
    for col in range(1, COL_CNT):
      curses.init_pair(col, col, COL_BG)
    while not self.quit:
      self.display()
      try:
        k = xlatkey(self.scr.getkey())
        self.handle_key(k)
      except KeyboardInterrupt:
        pass
    for col,(r,g,b) in default_colors.items():
      curses.init_color(col, r, g, b)

  def store_colors(self):
    if not default_colors:
      for col in range(COL_CNT):
        default_colors[col] = curses.color_content(col)

  def display(self):
    portable_erase(self.scr)
    maxy, maxx = self.scr.getmaxyx()
    syntax_lines = self.hiliter.syntax_lines[self.y:self.y+maxy]
    for sy, token_line in enumerate(syntax_lines[1:], 1):
      for token in token_line:
        s,sx = self.slice_token(maxx, token)
        if s:
          self.scr.addstr(sy, sx, s, curses.color_pair(token.col))
    s = ('DEBUG: ' + ' ~ '.join(debug_strs))[-maxx:]
    self.scr.addstr(0, 0, s, curses.color_pair(COL_BLOCK))
    self.scr.move(self.cy - self.y, self.vcx - self.x)
    self.scr.refresh()
  
  def handle_key(self, k):
    maxy, maxx = self.scr.getmaxyx()
    lowest_y = len(self.lines) - maxy + 1
    lowest_x = 2
    highest_x = maxx - 2
    line = self.lines[self.cy]
    if k == 'KEY_PPAGE':
      self.move_delta_yx(-maxy+1, 0, -maxy+1, 0)
    elif k == 'KEY_NPAGE':
      self.move_delta_yx(+maxy-1, 0, +maxy-1, 0)
    elif k == 'KEY_UP':
      self.move_delta_yx(-1, 0)
    elif k == 'KEY_DOWN':
      self.move_delta_yx(+1, 0)
    elif k == 'kUP5': # Ctrl+Up
      self.move_delta_yx(0, 0, -1, 0)
    elif k == 'kDN5': # Ctrl+Down
      self.move_delta_yx(0, 0, +1, 0)
    elif k == 'KEY_LEFT':
      self.move_delta_yx(0, -1)
    elif k == 'KEY_RIGHT':
      self.move_delta_yx(0, +1)
    elif k == 'kLFT5': # Ctrl+Left
      self.move_word(-1)
    elif k == 'kRIT5': # Ctrl+Right
      self.move_word(+1)
    elif k == 'KEY_HOME':
      self.move_delta_yx(0, int(-1e8))
    elif k == 'KEY_END':
      self.move_delta_yx(0, int(+1e8))
    elif k == 'kHOM5':
      self.move_delta_yx(int(-1e8), int(-1e8))
    elif k == 'kEND5':
      self.move_delta_yx(int(+1e8), int(+1e8))
    elif self.editable and k.isprintable() and len(k) == 1:
      self.cx = self.vcx
      self.lines[self.cy] = line[:self.cx] + k + line[self.cx:]
      self.move_delta_yx(0, +1)
      self.hiliter.hilite_line(self.cy, self.lines)
    elif self.editable and k == 'KEY_BACKSPACE':
      self.cx = self.vcx
      if self.cx > 0:
        self.lines[self.cy] = line[:self.cx-1] + line[self.cx:]
        self.move_delta_yx(0, -1)
      self.hiliter.hilite_line(self.cy, self.lines)
    elif self.editable and k == 'KEY_DC':
      self.cx = self.vcx
      self.lines[self.cy] = line[:self.cx] + line[self.cx+1:]
      self.hiliter.hilite_line(self.cy, self.lines)
    elif k in '\x18': # Ctrl+X
      self.cx = self.vcx
      self.quit = True
    else:
      print('key:', k.encode())

  def slice_token(self, maxx, token):
    x0 = max(0, self.x-token.x0)
    x1 = max(0, min(len(token.s), self.x+maxx-token.x0))
    s = token.s[x0:x1]
    sx = max(0, token.x0-self.x)
    return s, sx

  def move_delta_yx(self, dy, dx, sdy=0, sdx=0):
    maxy, maxx = self.scr.getmaxyx()
    # adjust screen position
    longest_line = max(len(l) for l in self.lines) if self.lines else 0
    self.y = max(0, min(len(self.lines)-maxy, self.y+sdy))
    self.x = max(0, min(longest_line-maxx//2, self.x+sdx))
    screen_rect = Rect(self.y, self.x, maxy, maxx)
    # adjust cursor position
    self.set_cursor_yx(self.cy+dy, self.cx+dx)
    if dx or dy:
      # scroll screen to follow cursor
      screen_rect.contain(Point(self.cy, self.vcx))
      self.y = screen_rect.y
      self.x = screen_rect.x
    else:
      # put cursor into screen
      cursor_pos = screen_rect.truncate(Point(self.cy, self.cx))
      self.set_cursor_yx(cursor_pos.y, cursor_pos.x)
    if dx:
      self.cx = self.vcx

  def set_cursor_yx(self, y, x):
    self.cy = max(0, min(len(self.lines)-1, y))
    self.vcx = max(0, min(len(self.lines[self.cy]), x))

  def move_word(self, direction):
    self.cx = self.vcx
    line = self.lines[self.cy]
    x = self.cx if direction>0 else self.cx-1
    step = +1 if direction>0 else -1
    matchers = [(not_txt,0), (is_txt,0)] if direction>0 else [(is_txt,0), (not_txt,+1)]
    for match,hit_moveback in matchers:
      while x+step >= 0 and x+step <= len(line):
        if x == len(line):
          break
        ch = line[x]
        if match(ch):
          x += hit_moveback
          break
        x += step
    self.move_delta_yx(0, x-self.cx)


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
