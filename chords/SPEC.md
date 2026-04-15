# Chord Chart DSL Specification

A minimal text-based format for writing chord charts with timing information.
File extension: `.chord`

## BNF Grammar

```bnf
<file>            ::= <header> <newline> <body>

; --- Header (metadata) ---
<header>          ::= <meta-line>+
<meta-line>       ::= "#" <space> <meta-key> ":" <space> <meta-value> <newline>
<meta-key>        ::= "title" | "metre" | "tempo" | "dromos" | "makam" | "key"
<meta-value>      ::= <text>

; --- Body (sections) ---
<body>            ::= <section>+
<section>         ::= <section-head> <newline> <line>+ <newline>
<section-head>    ::= "[" <section-name> "]"
<section-name>    ::= <text>                              ; Intro, San, Nakarat, Ara, Outro

; --- Lines ---
<line>            ::= <measure-line> | <comment-line> | <repeat-line>
<comment-line>    ::= "#" <space> <text> <newline>
<repeat-line>     ::= <repeat-open> | <repeat-close>
<repeat-open>     ::= "||:" <newline>
<repeat-close>    ::= ":||" [ <space> <repeat-count> ] <newline>
<repeat-count>    ::= "x" <integer>                       ; x2, x3

; --- Measures ---
<measure-line>    ::= "|" <measure> ( "|" <measure> )* <barline> <newline>
<barline>         ::= "|" | "||"                           ; normal or final
<measure>         ::= <space> <beat>+ <space>
<beat>            ::= <chord-beat> | <continuation> | <shorthand>
<chord-beat>      ::= <chord> ":" <duration>
<continuation>    ::= "-"                                  ; previous chord, same duration
<shorthand>       ::= ":" <duration> "{" <integer> "}"    ; N repetitions of duration
                     | "-" "{" <integer> "}"               ; N continuations

; --- Duration ---
<duration>        ::= "1" | "2" | "4" | "8" | "16"        ; standard note values
                     | <duration> "."                       ; dotted (1.5x)

; --- Chords ---
<chord>           ::= <root> [ <quality> ] [ <extension> ] [ "/" <root> ]
<root>            ::= "A" | "B" | "C" | "D" | "E" | "F" | "G"
                     | <root> "#" | <root> "b"
<quality>         ::= "m" | "dim" | "aug" | "sus2" | "sus4"
<extension>       ::= "7" | "maj7" | "m7" | "9" | "add9" | "6" | "5"
```

## Token Reference

| Token | Meaning | Example |
|-------|---------|---------|
| `Am:4` | Am, quarter note | 1 beat in 4/4 |
| `Am:8` | Am, eighth note | 0.5 beat in 4/4 |
| `Am:2` | Am, half note | 2 beats in 4/4 |
| `Am:1` | Am, whole note | 4 beats in 4/4 |
| `Am:4.` | Am, dotted quarter | 1.5 beats (quarter + eighth) |
| `Am:8.` | Am, dotted eighth | 0.75 beats (eighth + sixteenth) |
| `-` | Continue previous chord, same duration | `Am:8 - - = 3 eighths of Am` |
| `-{9}` | Continue previous chord N times | `Am:8 -{9} = 10 eighths of Am` |
| `\|` | Barline | separates measures |
| `\|\|` | Final barline | end of piece |
| `\|\|:` | Repeat open | start of repeated section |
| `:\|\|` | Repeat close | end of repeated section |
| `x2` | Repeat count | after `:||` |
| `[Name]` | Section header | `[Intro]`, `[San]`, `[Nakarat]` |
| `#` | Comment / metadata | `# title: ...` |

## Duration Values

Standard note value system — the number represents the fraction of a whole note:

| Value | Name | Duration (in quarter notes) |
|-------|------|-----------------------------|
| `1` | Whole (birlik) | 4 |
| `2` | Half (ikilik) | 2 |
| `4` | Quarter (dortluk) | 1 |
| `8` | Eighth (sekizlik) | 0.5 |
| `16` | Sixteenth (onaltilik) | 0.25 |
| `4.` | Dotted quarter | 1.5 |
| `8.` | Dotted eighth | 0.75 |
| `2.` | Dotted half | 3 |

## Metre & Measure Totals

Every measure must add up to the metre's total duration.

| Metre | Total (in quarter notes) | Common usage |
|-------|--------------------------|--------------|
| 2/4 | 2 | Hasapiko |
| 4/4 | 4 | Tsifteteli, Karsilamas |
| 3/4 | 3 | Vals |
| 7/8 | 3.5 | Kalamatiano (3+2+2) |
| 9/8 | 4.5 | Zeibekiko (2+2+2+3) |

## Section Names

| Name | Turkish | Usage |
|------|---------|-------|
| `Intro` | Giris | Opening instrumental |
| `San` | San | Vocal verse |
| `Nakarat` | Nakarat | Chorus/refrain |
| `Ara` | Ara | Instrumental bridge |
| `Outro` | Cikis | Ending |

## Examples

### Hasapiko (2/4)

```chord
# title: Hasapiko Politiko
# metre: 2/4
# tempo: 100
# dromos: Ousak

[Intro]
| Am:4 - | Dm:4 - | E7:4 - | Am:4 - |

[San]
||:
| Am:4 - | Am:4 - | Dm:4 - | Dm:4 - |
| E7:4 - | E7:4 - | Am:4 - | Am:4 - |
:|| x2

[Nakarat]
| Dm:4 - | Dm:4 - | Am:4 - | Am:4 - |
| E7:4 - | Am:4 - ||
```

### Zeibekiko (9/8)

9/8 = 4.5 quarter notes = 9 eighth notes per measure.

```chord
# title: Zeibekiko Example
# metre: 9/8
# tempo: 80
# dromos: Huseyni

[Intro]
| Am:8 - - Dm:8 - - Em:8 - - |
| Am:4. Dm:4. Em:4. |

[San]
| Am:8 -{8} |
| Dm:4. Em:4. Am:4. |
```

### Tsifteteli (4/4)

```chord
# title: Tsifteteli Example
# metre: 4/4
# tempo: 90
# makam: Hicaz

[Intro]
| Dm:4 - - - | Gm:4 - - - | A7:4 - - - | Dm:4 - - - |

[San]
||:
| Dm:4 - Gm:8 - - - | A7:4 - - - |
| Dm:4 - A7:4 - | Dm:4 - - - |
:||

[Ara]
| Gm:4 - - - | Dm:4 - A7:4 - |
| Dm:4 - - - ||
```

### Complex chords

```chord
# Chord names never clash with duration values:
| Cadd9:4 - C7:4 - |
| C5:2 Am7:2 |
| F#m:8 - - - Bbmaj7:8 - - - |
| Dsus4:4. E7/G#:8 |
```

## File Naming

Files stored in `chords/` directory:
```
chords/hasapiko_politiko.chord
chords/frangosyriani.chord
chords/tatavliano.chord
```

Convention: lowercase, underscores, ASCII transliteration of title.
