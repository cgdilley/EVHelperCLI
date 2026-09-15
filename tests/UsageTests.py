
from unittest import TestCase

from EVHelperCLI import *


class UsageTests(TestCase):

    def test_common_sets_cache(self):
        provider = UsageDataProvider()
        top_usage = provider.top_usage(limit=60)
        for tu in top_usage:
            try:
                cs = provider.common_sets(tu.pokemon.name.base_name())
                print(cs)
            except Exception as e:
                print(f"Error: {e}")
