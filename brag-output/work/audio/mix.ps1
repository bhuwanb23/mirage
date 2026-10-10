# Mix VO lines + music bed -> audio/master.wav (60s, 44.1k stereo)
# VO starts (v2 narrative):
#  n1@0.4 | sc1@3.5 | sc2@10.0 | sc3@17.3 (atrim 3.65s, cut by save @21)
#  n2@21.5 | n3@29.0 | n4@39.0 | n5@45.0 | n6@55.6
$ErrorActionPreference = "Stop"
$W = "D:\projects\website\mirage\brag-output\work"
$VO = "$W\vo"
$A = "$W\audio"

# Build VO bus: 60s track with each line delayed into place; sc3 trimmed mid-sentence at save
ffmpeg -y `
  -i "$VO\n1.wav" -i "$VO\sc1.wav" -i "$VO\sc2.wav" -i "$VO\sc3.wav" `
  -i "$VO\n2.wav" -i "$VO\n3.wav" -i "$VO\n4.wav" -i "$VO\n5.wav" -i "$VO\n6.wav" `
  -filter_complex "[0:a]adelay=400|400[a0];[1:a]adelay=3500|3500[a1];[2:a]adelay=10000|10000[a2];[3:a]atrim=0:3.65,adelay=17300|17300[a3];[4:a]adelay=21500|21500[a4];[5:a]adelay=29000|29000[a5];[6:a]adelay=39000|39000[a6];[7:a]adelay=45000|45000[a7];[8:a]adelay=55600|55600[a8];[a0][a1][a2][a3][a4][a5][a6][a7][a8]amix=inputs=9:normalize=0,apad,atrim=0:60,aresample=44100[out]" `
  -map "[out]" -ac 2 -c:a pcm_s16le "$A\vo_bus.wav"

# Duck music under VO: sidechaincompress keyed by VO bus; then mix
ffmpeg -y `
  -i "$A\music.wav" -i "$A\vo_bus.wav" `
  -filter_complex "[0:a][1:a]sidechaincompress=threshold=0.02:ratio=8:attack=80:release=400[duck];[duck][1:a]amix=inputs=2:normalize=0,alimiter=limit=0.891:level=disabled[out]" `
  -map "[out]" -ac 2 -c:a pcm_s16le "$A\master.wav"

ffprobe -v error -show_entries format=duration -of csv=p=0 "$A\master.wav"
