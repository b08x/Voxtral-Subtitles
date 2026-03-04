#!/bin/bash
# GPU Acceleration Test Script for Voxtral-Subtitles
# This script tests the difference between CPU and GPU video encoding

echo "🚀 NVIDIA GPU Acceleration Test for Voxtral-Subtitles"
echo "======================================================"

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Test if we have a sample video
TEST_VIDEO="examples/short_example.mp4"
if [ ! -f "$TEST_VIDEO" ]; then
    echo -e "${RED}❌ Test video not found: $TEST_VIDEO${NC}"
    echo "Please ensure you have example videos in the examples/ directory"
    exit 1
fi

echo -e "${GREEN}✅ Found test video: $TEST_VIDEO${NC}"

# Function to test encoding performance
test_encoding() {
    local encoder=$1
    local description=$2
    local output_suffix=$3

    echo ""
    echo -e "${YELLOW}Testing $description...${NC}"

    OUTPUT_FILE="test_output_${output_suffix}.mp4"

    # Remove previous test output
    rm -f "$OUTPUT_FILE"

    # Create a simple test subtitle file
    cat > test.ass << EOF
[Script Info]
Title: Test
ScriptType: v4.00+

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Arial,20,&H00FFFFFF,&H000000FF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,2,0,2,10,10,10,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
Dialogue: 0,0:00:01.00,0:00:05.00,Default,,0,0,0,,Test GPU Acceleration
EOF

    # Time the encoding process
    echo "Encoder: $encoder"
    time_start=$(date +%s.%N)

    ffmpeg -y -i "$TEST_VIDEO" -vf "ass=test.ass" -c:v "$encoder" -preset ultrafast -c:a copy "$OUTPUT_FILE" 2>/dev/null

    time_end=$(date +%s.%N)
    duration=$(echo "$time_end - $time_start" | bc)

    if [ -f "$OUTPUT_FILE" ]; then
        file_size=$(stat -c%s "$OUTPUT_FILE")
        echo -e "${GREEN}✅ Success${NC}"
        echo "   Duration: ${duration}s"
        echo "   Output size: $(($file_size / 1024))KB"
    else
        echo -e "${RED}❌ Failed${NC}"
        duration="FAILED"
    fi

    # Cleanup
    rm -f test.ass "$OUTPUT_FILE"

    echo "$duration"
}

# Test CPU encoding
echo ""
echo "==================== CPU ENCODING TEST ===================="
cpu_time=$(test_encoding "libx264" "CPU Encoding (libx264)" "cpu")

# Test GPU encoding (if available)
echo ""
echo "==================== GPU ENCODING TEST ===================="
if ffmpeg -encoders 2>/dev/null | grep -q h264_nvenc; then
    gpu_time=$(test_encoding "h264_nvenc" "GPU Encoding (NVENC)" "gpu")

    # Calculate performance difference
    if [ "$cpu_time" != "FAILED" ] && [ "$gpu_time" != "FAILED" ]; then
        echo ""
        echo "======================= RESULTS =========================="
        echo -e "${YELLOW}Performance Comparison:${NC}"
        echo "CPU Time: ${cpu_time}s"
        echo "GPU Time: ${gpu_time}s"

        # Calculate speedup (requires bc for floating point)
        if command -v bc >/dev/null 2>&1; then
            speedup=$(echo "scale=2; $cpu_time / $gpu_time" | bc)
            echo -e "${GREEN}GPU Speedup: ${speedup}x faster${NC}"

            if (( $(echo "$speedup > 2.0" | bc -l) )); then
                echo -e "${GREEN}🎉 Significant GPU acceleration achieved!${NC}"
            else
                echo -e "${YELLOW}⚠️  Modest GPU acceleration (short test video)${NC}"
            fi
        fi
    fi
else
    echo -e "${RED}❌ NVENC not available - GPU encoding skipped${NC}"
    echo "To enable GPU encoding:"
    echo "1. Set COMPUTE_DEVICE=CUDA in your .env file"
    echo "2. Start with: ./start.sh up nvidia --build"
fi

echo ""
echo "====================== RECOMMENDATIONS ==================="
echo -e "${YELLOW}To enable GPU acceleration in Voxtral-Subtitles:${NC}"
echo ""
echo "1. Add to .env file:"
echo "   COMPUTE_DEVICE=CUDA"
echo ""
echo "2. Start with GPU profile:"
echo "   ./start.sh up nvidia --build"
echo ""
echo "3. Configure Docker GPU runtime (if not already done):"
echo "   sudo apt-get install nvidia-container-toolkit"
echo "   sudo systemctl restart docker"
echo ""
echo "See NVIDIA_GPU_ANALYSIS.md for detailed instructions"