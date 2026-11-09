"""Optional local scientific runtime; normal installations use requirements.txt."""
import os,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
extra=os.environ.get('DG_SCIENCE_PATH')
if extra:sys.path.insert(0,extra)
elif (ROOT.parent/'Digital_Gardens_weather_recovery/runtime_packages').exists():
 sys.path.insert(0,str(ROOT.parent/'Digital_Gardens_weather_recovery/runtime_packages'))
os.environ.setdefault('NUMBA_NUM_THREADS','1')
os.environ.setdefault('OPENBLAS_NUM_THREADS','1')
os.environ.setdefault('OMP_NUM_THREADS','1')
