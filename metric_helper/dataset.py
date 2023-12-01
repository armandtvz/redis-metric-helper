import statistics as stats
from functools import cached_property

from metric_helper import utils




class Dataset:
    def __init__(self, data):
        if not isinstance(data, list):
            raise TypeError('"data" must be a list.')
        self.data = data


    def __str__(self):
        return str(self.data)


    def __iter__(self):
        for item in self.data:
            yield item


    def __len__(self):
        return len(self.data)


    def __getitem__(self, index):
        return self.data[index]


    @cached_property
    def values(self):
        _values = []
        for item in self.data:
            _values.append(item[1])
        return _values


    @cached_property
    def timestamps(self):
        _values = []
        for item in self.data:
            _values.append(item[0])
        return _values


    @cached_property
    def stdev(self):
        if len(self.values) < 2:
            return
        return stats.stdev(self.values)


    @cached_property
    def variance(self):
        if len(self.values) < 2:
            return
        return stats.variance(self.values)


    @cached_property
    def mean(self):
        if len(self.values) < 2:
            return
        return stats.mean(self.values)


    @property
    def avg(self):
        return self.mean


    @cached_property
    def median(self):
        if len(self.values) < 2:
            return
        return stats.median(self.values)


    @cached_property
    def mode(self):
        if len(self.values) < 2:
            return
        try:
            return stats.mode(self.values)
        except stats.StatisticsError:
            return


    def percentile(self, percent):
        if len(self.values) < 2:
            return
        self.values.sort()
        index = (percent / 100) * len(self.values)
        if index.is_integer():
            return self.values[int(index) - 1]
        return self.values[int(index)]


    def count(self):
        total = 0
        for item in self.data:
            total += item[1]

        if total == 0:
            return total

        if (total % int(total)) == 0:
            # Prevent returning something like 7.0.
            # Return 7 instead.
            return int(total)
        return total


    def min(self):
        if not self.values:
            return
        return min(self.values)


    def max(self):
        if not self.values:
            return
        return max(self.values)


    def draw(self, title, all_xticks=False, filename=None):
        if all_xticks:
            return utils.draw_all_xticks(self.data, title, filename=filename)
        return utils.draw(self.data, title, filename=filename)
