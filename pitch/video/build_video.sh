#!/bin/bash
set -e
cd /tmp/demo_video

VOICE="Samantha"
RATE=180   # words per minute (default 175 — slightly faster for tighter pacing)

# Per-scene texts (extracted from narration.txt for direct use)
declare -a SCENES=(
"Welcome to Inibsa Alert Marker by Mythos Group. This is the daily call list our system generates for Inibsa's six thousand dental clinics. The system has automatically flagged a client. Let's see what it found."
"The client is flagged as a lost client, with a clear next action: a periodic reminder. Two hundred eighty three days without a purchase, and a historic volume of around four thousand euros a year. Province, last purchase date, and average cycle are all visible at a glance."
"Crucial detail. Cycle status reads: overdue, ninety nine percent past the normal cycle. We are not flagging absolute silence; we are flagging silence that is abnormal for this specific client. The chart at the bottom confirms the drop in purchases over time."
"Switching to monitoring. The KPI strip splits all alerts into four sales-team-readable categories: lost clients, loss risk, sales opportunities, and healthy clients. No technical labels, just actions."
"Charts break alerts down by category and channel, and by province and product family. Most of the work falls on sales opportunities and loss risk, the actionable groups. Marketing automation absorbs low-priority alerts, freeing up the sales reps."
"The priority alert table is filterable, sortable, and exportable as CSV or as HubSpot Tasks JSON. The system is standalone today and CRM ready tomorrow, no rewrites needed."
"Final piece, the feedback loop. The disclaimer at the top makes it clear: these outcomes are mocked demo data, labelled as such. Real outcomes will flow in from the CRM. We already track conversion, false positives, and revenue captured."
"Capture window alerts convert at thirty three percent. Silent alerts at eleven percent. The system already shows which alert types pull their weight, and which ones need their thresholds tuned."
"Below, automatic threshold adjustment suggestions. When real outcomes accumulate, the system tunes its own rules. No retraining. No black box. Eight of eight brief deliverables shipped. Thank you for watching."
)

declare -a IMAGES=(
"01_client_view.png"
"02_client_metrics.png"
"03_client_chart.png"
"04_monitoring_top.png"
"05_monitoring_charts.png"
"06_monitoring_table.png"
"07_learning_top.png"
"08_learning_table.png"
"09_learning_recommendations.png"
)

# 1) Generate audio for each scene
echo "=== Generating audio ==="
rm -f audio_*.aiff audio_*.wav scene_*.mp4 concat_list.txt final.mp4
for i in "${!SCENES[@]}"; do
    n=$(printf "%02d" $((i+1)))
    say -v "$VOICE" -r "$RATE" -o "audio_${n}.aiff" "${SCENES[$i]}"
    # Convert to wav (16-bit PCM, 44.1kHz stereo) for ffmpeg compatibility
    afconvert -f WAVE -d LEI16@44100 -c 2 "audio_${n}.aiff" "audio_${n}.wav" 2>/dev/null
    dur=$(ffprobe -v error -show_entries format=duration -of csv=p=0 "audio_${n}.wav")
    echo "  scene $n: ${dur}s"
done

# 2) Build per-scene video clips (image displayed for audio duration)
echo "=== Building scene clips ==="
for i in "${!SCENES[@]}"; do
    n=$(printf "%02d" $((i+1)))
    img="${IMAGES[$i]}"
    aud="audio_${n}.wav"
    out="scene_${n}.mp4"
    dur=$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$aud")
    # Pad duration with 0.4s of silence at end to make transitions smoother
    pad=$(echo "$dur + 0.4" | bc)
    ffmpeg -y -loop 1 -i "$img" -i "$aud" -t "$pad" \
        -vf "scale=1920:1200:force_original_aspect_ratio=decrease,pad=1920:1200:(ow-iw)/2:(oh-ih)/2:white,format=yuv420p" \
        -c:v libx264 -tune stillimage -preset fast -crf 22 \
        -c:a aac -b:a 128k -ar 44100 -ac 2 \
        -shortest "$out" 2>/dev/null
    echo "  built $out (${pad}s)"
done

# 3) Concatenate into final
echo "=== Concatenating ==="
> concat_list.txt
for i in "${!SCENES[@]}"; do
    n=$(printf "%02d" $((i+1)))
    echo "file 'scene_${n}.mp4'" >> concat_list.txt
done

ffmpeg -y -f concat -safe 0 -i concat_list.txt -c copy final.mp4 2>/dev/null

# Report
total_dur=$(ffprobe -v error -show_entries format=duration -of csv=p=0 final.mp4)
total_size=$(stat -f%z final.mp4)
echo ""
echo "✅ /tmp/demo_video/final.mp4"
echo "   duration: ${total_dur}s"
echo "   size:     $((total_size / 1024)) KB"
