// Read-only evaluator snapshot for externally stopped budget-matched baselines.
#include "bridge.c"
API void study_snapshot(Pool* p, float* metrics) {
    for(int i=0;i<p->count;i++) {
        destination=metrics+i*12;study_capture(&p->envs[i],0);
    }
}
