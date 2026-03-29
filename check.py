# 检查所有方法
import inspect
print([method for method in dir(NearestNeighbourScorer) if not method.startswith('_')])