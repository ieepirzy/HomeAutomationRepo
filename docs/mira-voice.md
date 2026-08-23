# Mira voice rendering

Mira's identity and conversational behavior need their own prompt. Do not copy
the general `MIRA_SYSTEM` persona from `STT-Test/assistant-test.py`. The only
reusable prompt fragment from that demo is the renderer capability description
for xAI text-to-speech.

## Default language rule

Mira speaks Finnish by default. Include this requirement in Mira's own identity
prompt independently of the selected voice renderer:

```text
Speak Finnish by default. Use another language when Ila explicitly asks for it
or when preserving quoted/verbatim material. Keep established technical terms,
identifiers, commands and code in their natural form instead of forcing awkward
translations. Prefer natural conversational Finnish over literal translation.
```

xAI TTS does not currently list Finnish among its officially supported language
codes, although it notes that additional languages may work with varying
accuracy. For Finnish text, use `language: auto` rather than sending an
unsupported `fi` value. Ila has already used its Finnish synthesis and finds the
overall pronunciation surprisingly good despite the undocumented language,
with occasional edge cases during ordinary conversation. Treat those as a
quality limitation to monitor, not a reason to fall back to English.

## xAI TTS capability fragment

Attach this fragment only when the selected output route is synthesized by
xAI TTS:

```text
Your response will be spoken by xAI text-to-speech. You may use the following
speech controls when they make the delivery more natural.

Inline vocal events:
[pause] [long-pause] [hum-tune] [laugh] [chuckle] [giggle] [cry] [tsk]
[tongue-click] [lip-smack] [breath] [inhale] [exhale] [sigh]

Wrapping delivery styles:
<soft> <whisper> <loud> <build-intensity> <decrease-intensity>
<higher-pitch> <lower-pitch> <slow> <fast> <sing-song> <singing>
<laugh-speak> <emphasis>

Wrapping tags require a matching closing tag around a complete phrase, for
example: <whisper>It is a secret.</whisper>

Use controls sparingly and naturally. Do not mention or explain the tags in
the spoken response, and do not emit them when they add nothing to the delivery.
```

This is a rendering capability, not part of Mira's personality. The runtime
should append it to Mira's own system prompt for `speak_phone()` or any other
xAI-backed route. It should omit or replace the fragment for renderers that do
not support these tags; raw tags must never be read aloud by a fallback voice.

The tag set matches both the local STT demo and xAI's current TTS documentation.
Keep renderer capabilities versioned independently from Mira's identity prompt
so changing voice providers does not rewrite who Mira is.

Official reference: [xAI Text to Speech](https://docs.x.ai/developers/model-capabilities/audio/text-to-speech).
