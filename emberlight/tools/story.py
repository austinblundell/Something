"""
story.py -- the whole of EMBERLIGHT, as data.

Writing the script here rather than in assembly buys two things: prose can be
authored as ordinary sentences and word-wrapped to the dialogue box by the
build, and the pacing (fades, holds, weather changes) reads top to bottom like
a shooting script.

Emits assets/gen/story.inc: one ROMX section holding the opcode stream, every
string, and the explore-mode hotspot tables.
"""

TEXT_WIDTH = 18
TEXT_LINES = 3

# --- text control codes, mirroring defs.inc ---------------------------------
TX_END, TX_LINE, TX_PAGE, TX_PAUSE, TX_SPEED, TX_SHAKE, TX_SFX = range(7)

# --- opcodes ----------------------------------------------------------------
(OP_END, OP_PIC, OP_FADEIN, OP_FADEOUT, OP_TEXT, OP_BOXCLOSE, OP_WAIT,
 OP_WAITKEY, OP_FX, OP_SHAKE, OP_FLASH, OP_SFX, OP_MUSIC, OP_CHOICE,
 OP_JUMPIF, OP_JUMP, OP_SETVAR, OP_TITLE, OP_CARD, OP_EXPLORE, OP_PAN,
 OP_TEXTSPEED, OP_BEAT, OP_TENDFLAME, OP_CREDITS) = range(25)

FX_NONE, FX_RAIN, FX_RAIN_HEAVY, FX_EMBERS, FX_WATER, FX_GLINT, FX_SNOW = range(7)
SFX_BLIP, SFX_THUNDER, SFX_CHIME, SFX_WAVE = 1, 2, 3, 4
MUS_NIGHT, MUS_STORM, MUS_MEMORY = 1, 2, 3
VAR_CHOICE, VAR_OIL, VAR_LOG = 0, 1, 2


# ==========================================================================
#  text encoding
# ==========================================================================

def wrap(text):
    """Word-wrap prose to the dialogue box and page it automatically.

    A blank line in the source forces a page break; otherwise pages break
    every TEXT_LINES filled lines.  Returns a list of byte values.
    """
    out = bytearray()
    paragraphs = text.strip('\n').split('\n\n')
    lines = []
    breaks = set()
    for pi, para in enumerate(paragraphs):
        words = para.replace('\n', ' ').split()
        cur = ''
        for w in words:
            w = w.upper()
            if not cur:
                cur = w
            elif len(cur) + 1 + len(w) <= TEXT_WIDTH:
                cur += ' ' + w
            else:
                lines.append(cur)
                cur = w
        if cur:
            lines.append(cur)
        if pi != len(paragraphs) - 1:
            breaks.add(len(lines) - 1)          # page after this line

    on_page = 0
    for i, line in enumerate(lines):
        for ch in line:
            code = ord(ch)
            if code < 32 or code > 95:
                raise ValueError('character %r is outside the font' % ch)
            out.append(code)
        on_page += 1
        last = (i == len(lines) - 1)
        if last:
            break
        if on_page >= TEXT_LINES or i in breaks:
            out.append(TX_PAGE)
            on_page = 0
        else:
            out.append(TX_LINE)
    out.append(TX_END)
    return bytes(out)


def card(text):
    """Encode a chapter card: lines separated by TX_LINE, centred by the engine."""
    out = bytearray()
    for i, line in enumerate(text.strip('\n').split('\n')):
        line = line.strip().upper()
        if len(line) > 20:
            raise ValueError('card line too wide: %r' % line)
        if i:
            out.append(TX_LINE)
        out.extend(ord(c) for c in line)
    out.append(TX_END)
    return bytes(out)


MENU_WIDTH = TEXT_WIDTH - 1      # one column is spent on the cursor


def plain(text):
    """A single short line, no wrapping -- menu options and prompts."""
    t = text.upper()
    if len(t) > MENU_WIDTH:
        raise ValueError('menu option %r is %d wide, limit is %d'
                         % (t, len(t), MENU_WIDTH))
    return bytes(ord(c) for c in t) + bytes([TX_END])


# ==========================================================================
#  script builder
# ==========================================================================

class Script:
    def __init__(self):
        self.ops = []            # list of ('op', ...) / ('label', name) / refs
        self.blobs = {}          # name -> bytes
        self._n = 0

    # -- data ---------------------------------------------------------------
    def _blob(self, kind, data):
        self._n += 1
        name = 'txt_%s_%d' % (kind, self._n)
        self.blobs[name] = data
        return name

    def text(self, prose):
        name = self._blob('p', wrap(prose))
        self.ops.append((OP_TEXT, ('ref', name)))
        return self

    def say(self, who, prose):
        """Dialogue attributed to a speaker, in the house style."""
        return self.text('%s:\n%s' % (who.upper(), prose))

    # -- flow ---------------------------------------------------------------
    def label(self, name):
        self.ops.append(('label', name))
        return self

    def pic(self, bank_sym, pic_sym):
        self.ops.append((OP_PIC, ('bankof', pic_sym), ('sym', 'pic_' + pic_sym)))
        return self

    def fadein(self, speed=4):
        self.ops.append((OP_FADEIN, ('b', speed)))
        return self

    def fadeout(self, speed=4):
        self.ops.append((OP_FADEOUT, ('b', speed)))
        return self

    def wait(self, frames):
        self.ops.append((OP_WAIT, ('b', min(255, frames))))
        return self

    def beat(self, frames=40):
        self.ops.append((OP_BEAT, ('b', min(255, frames))))
        return self

    def waitkey(self):
        self.ops.append((OP_WAITKEY,))
        return self

    def boxclose(self):
        self.ops.append((OP_BOXCLOSE,))
        return self

    def fx(self, mode):
        self.ops.append((OP_FX, ('b', mode)))
        return self

    def shake(self, frames=20):
        self.ops.append((OP_SHAKE, ('b', frames)))
        return self

    def flash(self, n=1):
        self.ops.append((OP_FLASH, ('b', n)))
        return self

    def sfx(self, i):
        self.ops.append((OP_SFX, ('b', i)))
        return self

    def music(self, i):
        self.ops.append((OP_MUSIC, ('b', i)))
        return self

    def title(self):
        self.ops.append((OP_TITLE,))
        return self

    def card(self, lines):
        name = self._blob('c', card(lines))
        self.ops.append((OP_CARD, ('ref', name)))
        return self

    def credits(self, lines):
        name = self._blob('c', card(lines))
        self.ops.append((OP_CREDITS, ('ref', name)))
        return self

    def textspeed(self, n):
        self.ops.append((OP_TEXTSPEED, ('b', n)))
        return self

    def setvar(self, var, val):
        self.ops.append((OP_SETVAR, ('b', var), ('b', val)))
        return self

    def jump(self, label):
        self.ops.append((OP_JUMP, ('lbl', label)))
        return self

    def jumpif(self, var, val, label):
        self.ops.append((OP_JUMPIF, ('b', var), ('b', val), ('lbl', label)))
        return self

    def choice(self, prompt, opt_a, opt_b):
        p = self._blob('q', wrap(prompt))
        a = self._blob('a', plain(opt_a))
        b = self._blob('b', plain(opt_b))
        self.ops.append((OP_CHOICE, ('ref', p), ('ref', a), ('ref', b)))
        return self

    def tendflame(self):
        self.ops.append((OP_TENDFLAME,))
        return self

    def explore(self, spots):
        """spots: list of (x, y, w, h, prose, flags)."""
        entries = []
        for (x, y, w, h, prose, flags) in spots:
            name = self._blob('s', wrap(prose))
            entries.append((x, y, w, h, name, flags))
        self._n += 1
        tname = 'spots_%d' % self._n
        self.blobs[tname] = ('spots', entries)
        self.ops.append((OP_EXPLORE, ('ref', tname)))
        return self

    def end(self):
        self.ops.append((OP_END,))
        return self

    # -- emission -----------------------------------------------------------
    def emit(self, section_bank):
        L = []
        L.append('; ==========================================================')
        L.append(';  EMBERLIGHT -- story script (generated by tools/story.py)')
        L.append('; ==========================================================')
        L.append('SECTION "story", ROMX, BANK[%d]' % section_bank)
        L.append('')
        L.append('Story::')
        for op in self.ops:
            if op[0] == 'label':
                L.append('.%s:' % op[1])
                continue
            code = op[0]
            args = op[1:]
            parts = []
            for a in args:
                kind, val = a
                if kind == 'b':
                    parts.append(('db', str(val)))
                elif kind == 'ref':
                    parts.append(('dw', val))
                elif kind == 'sym':
                    parts.append(('dw', val))
                elif kind == 'bankof':
                    parts.append(('db', 'BANK(pic_%s)' % val))
                elif kind == 'lbl':
                    parts.append(('dw', 'Story.%s' % val))
            L.append('    db  $%02X' % code + ('' if not parts else
                     '                 ; ' + OPNAMES.get(code, '')))
            for (d, v) in parts:
                L.append('    %s  %s' % (d, v))
        L.append('')

        # --- strings and hotspot tables ---
        for name, data in self.blobs.items():
            if isinstance(data, tuple) and data[0] == 'spots':
                L.append('%s:' % name)
                L.append('    db  %d' % len(data[1]))
                for (x, y, w, h, ref, flags) in data[1]:
                    L.append('    db  %d, %d, %d, %d' % (x, y, w, h))
                    L.append('    dw  %s' % ref)
                    L.append('    db  $%02X' % flags)
                L.append('')
        for name, data in self.blobs.items():
            if isinstance(data, tuple):
                continue
            L.append('%s:' % name)
            for i in range(0, len(data), 16):
                chunk = data[i:i + 16]
                L.append('    db ' + ','.join('$%02X' % b for b in chunk))
            L.append('')
        return '\n'.join(L)


OPNAMES = {
    OP_PIC: 'PIC', OP_FADEIN: 'FADEIN', OP_FADEOUT: 'FADEOUT', OP_TEXT: 'TEXT',
    OP_WAIT: 'WAIT', OP_FX: 'FX', OP_SHAKE: 'SHAKE', OP_FLASH: 'FLASH',
    OP_SFX: 'SFX', OP_MUSIC: 'MUSIC', OP_CHOICE: 'CHOICE', OP_JUMPIF: 'JUMPIF',
    OP_JUMP: 'JUMP', OP_SETVAR: 'SETVAR', OP_CARD: 'CARD', OP_EXPLORE: 'EXPLORE',
    OP_TEXTSPEED: 'TEXTSPEED', OP_BEAT: 'BEAT', OP_TENDFLAME: 'TENDFLAME',
    OP_CREDITS: 'CREDITS',
}

SPOTF_EXIT = 0x80
SPOTF_SETV = 0x40


# ==========================================================================
#  THE STORY
# ==========================================================================

def build():
    s = Script()

    # ---------------------------------------------------------------- title
    s.pic(None, 'title')
    s.music(MUS_NIGHT)
    s.fx(FX_GLINT)
    s.title()

    # ------------------------------------------------------------- prologue
    s.card("""
EMBERLIGHT

CHAPTER ONE
THE NIGHT THE
LAMP WENT OUT
""")

    s.pic(None, 'storm')
    s.music(MUS_STORM)
    s.fx(FX_RAIN_HEAVY)
    s.fadein(5)
    s.beat(50)
    s.sfx(SFX_THUNDER)
    s.flash(2)
    s.shake(24)
    s.textspeed(2)
    s.text("""
The sea has been
climbing for a hundred years.

It took the low fields, then the
lane, then the church. It is
taking the rest slowly, the way
a patient animal eats.

One light is left on this coast.
Mine.
""")
    s.text("""
My name is Mira Cale. I am
seventeen years old and I am
the keeper of Emberlight.

My father was keeper before me.
He is not the keeper now.
""")
    s.boxclose()
    s.beat(40)
    s.sfx(SFX_THUNDER)
    s.shake(30)

    # ----------------------------------------------------------- lamp room
    s.pic(None, 'lamproom')
    s.fx(FX_EMBERS)
    s.fadein(4)
    s.beat(40)
    s.text("""
The flame in the lamp of
Emberlight has never once been
lit from a match.

It was carried here in an iron
box by the first keeper, and
every keeper since has fed it
and kept it and passed it on.

Tonight it is the size of my
thumbnail.
""")
    s.boxclose()
    s.beat(30)

    s.text("""
Look around. Press A on
whatever holds your eye.
""")
    s.boxclose()

    s.explore([
        (58, 44, 44, 44,
         """
         The ember.

         It is down to a bead of
         orange in a bed of grey. When
         I breathe on it, it answers.
         When I stop, it forgets.
         """, SPOTF_SETV | VAR_LOG),
        (10, 12, 40, 82,
         """
         The east window.

         Rain going sideways. Out
         there, somewhere, the shipping
         lane, and men who have decided
         to trust me tonight.
         """, 0),
        (114, 12, 44, 82,
         """
         The west window.

         Below it the drowned village,
         and the roof I was born under,
         four feet down in black water.
         """, 0),
        (20, 106, 40, 30,
         """
         The logbook, open where he
         left it.

         A LIGHT OFF THE SHOALS,
         SIGNALLING. THREE SHORT, ONE
         LONG. GOING OUT TO IT.

         That is the last thing my
         father wrote.
         """, SPOTF_SETV | VAR_LOG),
        (64, 100, 40, 36,
         """
         The bellows, and the last of
         the oil.

         Enough for one night. If I am
         going to do this, it has to be
         now.
         """, SPOTF_EXIT),
    ])

    # ---------------------------------------------------- tend the flame
    s.text("""
Kneel. Cup your hands. Breathe
the way he taught you, slow and
from the bottom of your chest.
""")
    s.boxclose()
    s.tendflame()
    s.text("""
The ember takes. The lens
throws a road of light out onto
the water, and for a moment the
whole storm is lit from inside.

I am still the keeper.
""")
    s.boxclose()
    s.fadeout(4)

    # ------------------------------------------------- chapter two: village
    s.card("""
CHAPTER TWO

THE DROWNED
VILLAGE
""")

    s.pic(None, 'village')
    s.music(MUS_MEMORY)
    s.fx(FX_WATER)
    s.fadein(6)
    s.beat(60)
    s.textspeed(3)
    s.text("""
The oil is gone. There is more
in the storehouse, and the
storehouse is under the sea.

So I go out over the top of my
own village in my father's
boat, with a lantern on the
bow.
""")
    s.text("""
That gable is the Alder house.
That chimney is the forge.

The flat black water between
them is the square where I
learned to run.

Nobody screams when a place
drowns. It just gets quieter
every year until it is gone.
""")
    s.boxclose()
    s.beat(50)
    s.sfx(SFX_WAVE)
    s.beat(30)

    s.text("""
Then, off the shoals, out where
there is nothing at all -

a light.

Three short. One long.
""")
    s.boxclose()
    s.flash(1)
    s.beat(30)
    s.text("""
The same signal. The same
place. The same patient,
reasonable little light that
took my father.
""")
    s.boxclose()
    s.fadeout(5)

    # --------------------------------------------------- chapter three
    s.card("""
CHAPTER THREE

THE SIGNAL
""")

    s.pic(None, 'signal')
    s.music(MUS_STORM)
    s.fx(FX_RAIN)
    s.fadein(5)
    s.beat(50)
    s.text("""
Here is the arithmetic, and it
is not difficult.

If I row out to the shoals I
will not be back before the
ember dies. Emberlight will go
dark tonight, and it will stay
dark, because there is no more
oil and no more keeper.
""")
    s.text("""
If I turn around and go back to
my tower, the light stays lit
for every ship on this coast.

Except one.
""")
    s.boxclose()
    s.beat(40)

    s.choice("""
Three short. One long.

What do you do?
""", "ROW OUT TO IT", "KEEP THE LIGHT")

    s.jumpif(VAR_CHOICE, 2, 'keeps_the_light')

    # ---------------------------------------------------------- ending A
    s.label('rows_out')
    s.pic(None, 'rescue')
    s.fx(FX_RAIN_HEAVY)
    s.fadein(4)
    s.shake(30)
    s.beat(40)
    s.text("""
I row. It takes an hour and it
costs me both hands.

There is a boat on the shoals
with four men in it and a
storm lantern they have been
swinging since dusk.

They are alive. All four of
them are alive.
""")
    s.text("""
Behind me, out on the point,
Emberlight burns down to
nothing and goes out.

I watch it go. I am the keeper
who let the light die, and
there are four men in my boat
who will say I am something
else.

Both of those are true. I have
stopped trying to make them
agree.
""")
    s.boxclose()
    s.fadeout(6)
    s.jump('dawn')

    # ---------------------------------------------------------- ending B
    s.label('keeps_the_light')
    s.pic(None, 'vigil')
    s.fx(FX_RAIN)
    s.fadein(4)
    s.beat(40)
    s.text("""
I go back. I climb the stair I
have climbed ten thousand
times, and I feed the ember,
and I keep the light.

The signal goes on for two
hours. Three short. One long.

Then it stops.
""")
    s.text("""
Nine ships passed the point
that night. I counted every
one. Nine crews went home to
somebody.

That is the number I say to
myself. It is a good number.
It has never once been enough.
""")
    s.boxclose()
    s.fadeout(6)

    # ------------------------------------------------------------- dawn
    s.label('dawn')
    s.card("""
CHAPTER FOUR

DAWN
""")

    s.pic(None, 'dawn')
    s.music(MUS_MEMORY)
    s.fx(FX_GLINT)
    s.fadein(8)
    s.beat(70)
    s.textspeed(3)
    s.text("""
The sea goes flat at dawn the
way a dog lies down.

You would not believe, looking
at it, that it had done
anything at all.
""")

    s.jumpif(VAR_CHOICE, 2, 'dawn_kept')

    s.text("""
The tower on the point is
dark, and it will stay dark.
Emberlight kept a hundred and
eleven years and I am the one
who put it out.

Four men are asleep on my
kitchen floor.

I would do it again. That is
the whole of what I know.
""")
    s.jump('dawn_join')

    s.label('dawn_kept')
    s.text("""
The tower on the point is
still burning, pale and silly
in the daylight, the way it
does every morning.

Somewhere off the shoals there
is an empty boat.

I keep the light. That is the
whole of what I know.
""")

    s.label('dawn_join')
    s.boxclose()
    s.beat(40)
    s.text("""
My father used to say that a
lighthouse is a promise you
make to people you will never
meet.

He never said it was a promise
you could keep.
""")
    s.boxclose()
    s.fadeout(8)

    s.credits("""
EMBERLIGHT


KEEPER OF THE
LAST LIGHT


THANK YOU
FOR PLAYING
""")

    s.pic(None, 'title')
    s.fx(FX_GLINT)
    s.music(MUS_NIGHT)
    s.fadein(8)
    s.beat(255)
    s.end()
    return s
