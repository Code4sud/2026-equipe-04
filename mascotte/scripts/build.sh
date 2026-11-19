#!/bin/zsh
# Regenere neo.glb et neo.blend. Source attendue : ~/Downloads/Meshy_AI_Skytrail_Fox_1118154310_texture.glb
set -e
cd "${0:A:h}"; B=/Applications/Blender.app/Contents/MacOS/Blender
[[ -f low.blend ]] || $B -b --factory-startup --python-exit-code 1 -P s3_retopo.py
$B -b low.blend --python-exit-code 1 -P s5_rig.py
$B -b rig.blend --python-exit-code 1 -P s8_export.py
mv neo.glb neo.blend ..
