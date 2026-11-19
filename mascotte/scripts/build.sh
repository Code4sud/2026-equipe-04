#!/bin/zsh
# Regenere neo.glb et neo.blend depuis le modele Meshy cartoon (par defaut ~/Downloads/cartoon.glb).
# Necessite le skill rig-animate-glb pour la preparation du mesh.
set -e
cd "${0:A:h}"; B=/Applications/Blender.app/Contents/MacOS/Blender; SRC="${1:-$HOME/Downloads/cartoon.glb}"
RUN=~/.claude/skills/rig-animate-glb/scripts/run.sh
if [[ ! -f low.blend ]]; then
  $RUN prepare "$SRC" . --tris 30000 --focus "-.32,.32,-.6,-.15,.24,.72,2" --dense ".12,.451,.061,.068;-.12,.451,.061,.068"
  cp base.png fox_base.png; cp normal.png fox_normal.png
fi
$B -b low.blend --python-exit-code 1 -P s5_rig.py
$B -b rig.blend --python-exit-code 1 -P s8_export.py
mv neo.glb neo.blend ..
