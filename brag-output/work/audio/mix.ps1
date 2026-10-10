# Mix VO lines + music bed -> audio/master.wav (60s, 44.1k stereo)
# VO starts (from brag-plan.md storyboard):
#  s1 0.4 | s2 3.6 | s3 9.0 | s4 22.0 | s5 37.0 | s6 48.0 | s7 55.4
$ErrorActionPreference = "Stop"
$W = "D:\projects\website\mirage\brag-output\work"
$VO = "$W\vo"
$A = "$W\audio"

# Build VO bus: 60s track with each line delayed into place
ffmpeg -y `
  -i "$VO\s1.wav" -i "$VO\s2.wav" -i "$VO\s3.wav" -i "$VO\s4.wav" `
  -i "$VO\s5.wav" -i "$VO\s6.wav" -i "$VO\s7.wav" `
  -filter_complex "[0:a]adelay=400|400[a0];[1:a]adelay=3600|3600[a1];[2:a]adelay=9000|9000[a2];[3:a]adelay=22000|22000[a3];[4:a]adelay=37000|37000[a4];[5:a]adelay=48000|48000[a5];[6:a]adelay=55400|55400[a6];[a0][a1][a2][a3][a4][a5][a6]amix=inputs=7:normalize=0,apad,atrim=0:60,aresample=44100[out]" `
  -map "[out]" -ac 2 -c:a pcm_s16le "$A\vo_bus.wav"

# Duck music under VO: sidechaincompress keyed by VO bus; then mix
ffmpeg -y `
  -i "$A\music.wav" -i "$A\vo_bus.wav" `
  -filter_complex "[0:a][1:a]sidechaincompress=threshold=0.02:ratio=8:attack=80:release=400[duck];[duck][1:a]amix=inputs=2:normalize=0,alimiter=limit=0.891:level=disabled[out]" `
  -map "[out]" -ac 2 -c:a pcm_s16le "$A\master.wav"

ffprobe -v error -show_entries format=duration -of csv=p=0 "$A\master.wav"
