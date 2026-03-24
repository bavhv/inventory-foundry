#!/bin/bash

################################################################################
# Script: compare_users.sh
# Purpose: Compare 2 user files → common, only-in-A, only-in-B
# Enhancements:
#   ✅ Logging with timestamps
#   ✅ Show duration of script
#   ✅ Remove duplicates (keep first occurrence only)
################################################################################

start_time=$(date +%s)
echo "🚀 Script started at: $(date)"

fileA="ags_members.txt"
fileB="team_members.txt"
logFile="compare_users.log"

echo "" | tee "$logFile"
echo "========== USER COMPARISON SCRIPT ==========" | tee -a "$logFile"
echo "Start Time: $(date)" | tee -a "$logFile"
echo "============================================" | tee -a "$logFile"
echo "" | tee -a "$logFile"

echo "📁 Input Files: $fileA and $fileB" | tee -a "$logFile"

echo "🧹 Step 1: Normalizing input files for comparison..." | tee -a "$logFile"

# Create working directory
mkdir -p _normalized

# Normalize function
normalize_file() {
    input="$1"
    output="$2"

    awk '
    {
        orig=$0
        norm=tolower($0)
        gsub(/[^a-z0-9]/, "", norm)
        print orig "\t" norm
    }' "$input" > "$output"
}

normalize_file "$fileA" "_normalized/A_norm.txt"
normalize_file "$fileB" "_normalized/B_norm.txt"

echo "🔎 Step 2: Creating sorted normalized lists..." | tee -a "$logFile"
cut -f2 "_normalized/A_norm.txt" | sort > "_normalized/A_norm_sorted.txt"
cut -f2 "_normalized/B_norm.txt" | sort > "_normalized/B_norm_sorted.txt"

echo "🤝 Step 3: Identifying common & unique users..." | tee -a "$logFile"

# Common normalized keys
comm -12 "_normalized/A_norm_sorted.txt" "_normalized/B_norm_sorted.txt" > "_normalized/common_norm.txt"

echo "🧠 Step 4: Mapping results back to original values..." | tee -a "$logFile"

# Prepare output files
> common_users.txt
> only_in_AGS.txt
> only_in_GH_Teams.txt

# Create temp maps (norm → original)
awk -F'\t' '{print $2"\t"$1}' _normalized/A_norm.txt > _normalized/A_map.txt
awk -F'\t' '{print $2"\t"$1}' _normalized/B_norm.txt > _normalized/B_map.txt

# COMMON
while IFS= read -r norm; do
    grep -F "$norm" _normalized/A_map.txt | cut -f2 >> common_users.txt
    grep -F "$norm" _normalized/B_map.txt | cut -f2 >> common_users.txt
done < _normalized/common_norm.txt

# ONLY IN A
grep -vFf "_normalized/B_norm_sorted.txt" "_normalized/A_norm_sorted.txt" > "_normalized/onlyA_norm.txt"
while IFS= read -r norm; do
    grep -F "$norm" _normalized/A_map.txt | cut -f2 >> only_in_AGS.txt
done < _normalized/onlyA_norm.txt

# ONLY IN B
grep -vFf "_normalized/A_norm_sorted.txt" "_normalized/B_norm_sorted.txt" > "_normalized/onlyB_norm.txt"
while IFS= read -r norm; do
    grep -F "$norm" _normalized/B_map.txt | cut -f2 >> only_in_GH_Teams.txt
done < _normalized/onlyB_norm.txt

echo "🧽 Step 5: Removing duplicates from output files (keeping first occurrence)..." | tee -a "$logFile"
mv common_users.txt common_tmp.txt && awk '!seen[$0]++' common_tmp.txt > common_users.txt
mv only_in_AGS.txt onlyA_tmp.txt && awk '!seen[$0]++' onlyA_tmp.txt > only_in_AGS.txt
mv only_in_GH_Teams.txt onlyB_tmp.txt && awk '!seen[$0]++' onlyB_tmp.txt > only_in_GH_Teams.txt

echo "📊 Step 6: Generating counts..." | tee -a "$logFile"

countA=$(wc -l < "$fileA")
countB=$(wc -l < "$fileB")
countCommon=$(wc -l < common_users.txt)
countOnlyA=$(wc -l < only_in_AGS.txt)
countOnlyB=$(wc -l < only_in_GH_Teams.txt)

echo "" | tee -a "$logFile"
echo "📊 Input Counts" | tee -a "$logFile"
echo " - AGS: $countA" | tee -a "$logFile"
echo " - GH Teams: $countB" | tee -a "$logFile"

echo "" | tee -a "$logFile"
echo "✅ Common Users: $countCommon (common_users.txt)" | tee -a "$logFile"
echo "❗ Only in AGS: $countOnlyA (only_in_AGS.txt)" | tee -a "$logFile"
echo "❗ Only in GH Teams: $countOnlyB (only_in_GH_Teams.txt)" | tee -a "$logFile"
echo "" | tee -a "$logFile"
echo "📁 Output files generated:" | tee -a "$logFile"
echo " - common_users.txt" | tee -a "$logFile"
echo " - only_in_AGS.txt" | tee -a "$logFile"
echo " - only_in_GH_Teams.txt" | tee -a "$logFile"

end_time=$(date +%s)
duration=$((end_time - start_time))

echo "" | tee -a "$logFile"
echo "🏁 Script completed at: $(date)" | tee -a "$logFile"
echo "⏱️ Total Execution Time: ${duration} seconds" | tee -a "$logFile"
echo "" | tee -a "$logFile"
echo "✅ Done. Check the log at $logFile"
echo ""
