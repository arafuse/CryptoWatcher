# -*- coding: utf-8 -*-

# Copyright (c) A 2017 Adam M. Rafuse - All Rights Reserved
# Unauthorized copying of this file, via any medium is strictly prohibited
# Proprietary and confidential

"""
Detection definitions.
"""

__author__ = 'Adam Rafuse <$(echo nqnz.enshfr#tznvy.pbz | tr a-z# n-za-m@)>'

# Buy detection that catches dips.
BUY_RETRACEMENT_0 = {
    'retracement0init0': {
        'type': 'init0',
        'groups': ['retracement_0_0'],
        'action': 'none',
        'time_frame_max': 1800,
        'value_range_max': None,
        'conditions': [
            [
                ('ma_position', 6, 5),
                ('ma_crossover', 3, 2),
            ]
        ]
    },

    'retracement0init1': {
        'type': 'init1',
        'groups': ['retracement_0_0'],
        'action': 'none',
        'time_frame_max': 1800,
        'value_range_max': None,
        'follow': [
            {
                'groups': ['retracement_0_0'],
                'types': ['init0'],
                'min_secs': 0,
                'max_secs': None,
            }
        ],
        'conditions': [
            [
                ('ma_slope_max', 6, -0.215),  # -0.2
                ('ma_slope_max', 5, -0.215),  # -0.235
                ('ma_slope_max', 4, -0.085),
                ('ma_slope_max', 3, 0.0),
                ('ma_slope_max', 2, 0.0),
                ('ma_slope_max', 1, 0.0),
                ('ma_crossover', 0, 1),
            ],
        ]
    },

    'retracement0confirm0': {
        'type': 'confirm0',
        'groups': ['retracement_0_0'],
        'action': 'buy',
        'occurrence': 1,
        'time_frame_max': 1800,
        'value_range_max': None,
        'rebuy': False,
        'overlap': None,
        'push_max': 2,
        'soft_max': 1,
        'deferred_push': False,
        'push_target': 0.06,
        'stop_percent': 0.35,
        'stop_cutoff': 0.035,
        'follow': [
            {
                'groups': ['retracement_0_0'],
                'types': ['init1'],
                'min_secs': 0,
                'max_secs': None
            },
        ],
        'conditions': [
            [
                ('ma_crossover', 0, 2),
            ],
        ]
    },
}

# Buy detection that catches dips.
BUY_RETRACEMENT_1 = {
    'retracement1init0': {
        'type': 'init0',
        'groups': ['retracement_1_0'],
        'action': 'none',
        'time_frame_max': 1800,
        'value_range_max': None,
        'conditions': [
            [
                ('ma_crossover', 3, 2),
            ]
        ]
    },

    'retracement1init1': {
        'type': 'init1',
        'groups': ['retracement_1_0'],
        'action': 'none',
        'time_frame_max': 1800,
        'value_range_max': None,
        'follow': [
            {
                'groups': ['retracement_1_0'],
                'types': ['init0'],
                'min_secs': 60 * 90,
                'max_secs': None,
            }
        ],
        'conditions': [
            [
                ('ma_position', 4, 3),
                ('ma_position', 3, 2),
                ('ma_position', 2, 1),
                ('ma_slope_max', 4, -0.5),
                ('ma_slope_max', 3, -0.85),
                ('ma_slope_max', 2, -1.0),
                ('ma_slope_min', 1, -0.5),
                ('ma_crossover', 0, 1),
            ],
        ]
    },

    'retracement1confirm0': {
        'type': 'confirm0',
        'groups': ['retracement_1_0'],
        'action': 'buy',
        'occurrence': 1,
        'time_frame_max': 1800,
        'value_range_max': None,
        'rebuy': False,
        'overlap': None,
        'push_max': 2,
        'soft_max': 1,
        'deferred_push': False,
        'push_target': 0.04,
        'stop_percent': 0.25,
        'stop_cutoff': 0.035,
        'follow': [
            {
                'groups': ['retracement_1_0'],
                'types': ['init1'],
                'min_secs': 0,
                'max_secs': None
            },
        ],
        'conditions': [
            [
                ('ma_position', 4, 3),
                ('ma_position', 3, 2),
                ('ma_position', 2, 1),
                ('ma_crossover', 0, 2),
            ],
        ]
    },
}

# Buy detection that catches dips.
BUY_RETRACEMENT_2 = {
    'retracement2init0': {
        'type': 'init0',
        'groups': ['retracement_2_0'],
        'action': 'none',
        'time_frame_max': 1800,
        'value_range_max': None,
        'conditions': [
            [
                ('ma_crossover', 3, 2),
            ]
        ]
    },

    'retracement2init1': {
        'type': 'init1',
        'groups': ['retracement_2_0'],
        'action': 'none',
        'time_frame_max': 1800,
        'value_range_max': None,
        'follow_all': [
            {
                'groups': ['retracement_2_0'],
                'types': ['init0'],
                'min_secs': 0,
                'max_secs': None
            }
        ],
        'conditions': [
            [
                ('ma_position', 4, 3),
                ('ma_position', 3, 2),
                ('ma_position', 2, 1),
                ('ma_slope_max', 4, -0.135),
                ('ma_slope_max', 3, -0.85),
                ('ma_slope_max', 2, -1.35),
                ('ma_slope_max', 1, -2.0),
                ('ma_crossover', 0, 1),
            ],
        ]
    },

    'retracement2confirm0': {
        'type': 'confirm0',
        'groups': ['retracement_2_0'],
        'action': 'buy',
        'occurrence': 1,
        'time_frame_max': 1800,
        'value_range_max': None,
        'rebuy': False,
        'overlap': None,
        'push_max': 2,
        'soft_max': 1,
        'deferred_push': False,
        'push_target': 0.04,
        'stop_percent': 0.25,
        'stop_cutoff': 0.035,
        'follow': [
            {
                'groups': ['retracement_2_0'],
                'types': ['init1'],
                'min_secs': 0,
                'max_secs': None
            },
        ],
        'conditions': [
            [
                ('ma_position', 4, 3),
                ('ma_position', 3, 2),
                ('ma_position', 2, 1),
                ('ma_crossover', 0, 2),
            ],
        ]
    },
}

# Buy detection that catches reversals after a bottom / top pattern.
BUY_REVERSAL_0 = {
    'reversal0init0': {
        'type': 'init0',
        'groups': ['reversal_0_0', 'reversal_0_1'],
        'action': 'none',
        'time_frame_max': 1800,
        'value_range_max': None,
        'conditions': [
            [
                ('ma_crossover', 6, 3),
                ('ma_position', 3, 2),
                ('ma_position', 3, 1),
                ('ma_position', 3, 0),
            ],
        ]
    },

    'reversal0init1': {
        'type': 'init1',
        'groups': ['reversal_0_0', 'reversal_0_bottom'],
        'action': 'none',
        'time_frame_max': 1800,
        'value_range_max': None,
        'follow': [
            {
                'groups': ['reversal_0_0'],
                'types': ['init0'],
                'min_secs': 0,
                'max_secs': None
            },
            {
                'groups': ['reversal_0_0'],
                'types': ['init1'],
                'min_secs': 0,
                'max_secs': None,
                'max_delta': 0.0
            }
        ],
        'conditions': [
            [
                ('ma_crossover', 0, 3),
            ],
        ]
    },

    'reversal0init2': {
        'type': 'init2',
        'groups': ['reversal_0_0', 'reversal_0_1', 'reversal_0_2'],
        'action': 'none',
        'time_frame_max': 1800,
        'value_range_max': None,
        'follow': [
            {
                'groups': ['reversal_0_0'],
                'types': ['init1'],
                'min_secs': 0,
                'max_secs': None
            }
        ],
        'conditions': [
            [
                ('ma_crossover', 3, 6),
                ('ma_position', 0, 3),
                ('ma_position', 1, 3),
                ('ma_position', 2, 3),
            ],
        ]
    },

    'reversal0init3': {
        'type': 'init3',
        'groups': ['reversal_0_0'],
        'action': 'none',
        'time_frame_max': 1800,
        'value_range_max': None,
        'follow': [
            {
                'groups': ['reversal_0_0'],
                'types': ['init2'],
                'min_secs': 0,
                'max_secs': None
            },
        ],
        'conditions': [
            [
                ('ma_crossover', 3, 0),
            ],
        ]
    },

    'reversal0init3a': {
        'type': 'init3a',
        'groups': ['reversal_0_0'],
        'action': 'none',
        'time_frame_max': 1800,
        'value_range_max': None,
        'follow': [
            {
                'groups': ['reversal_0_0'],
                'types': ['init3'],
                'min_secs': 60,
                'max_secs': None,
                'min_delta': 0.0,
            },
        ],
        'conditions': [
            [
                ('ma_crossover', 3, 0),
            ],
        ]
    },

    'reversal0init3b': {
        'type': 'init3b',
        'groups': ['reversal_0_0', 'reversal_0_top'],
        'action': 'none',
        'time_frame_max': 1800,
        'value_range_max': None,
        'follow': [
            {
                'groups': ['reversal_0_0'],
                'types': ['init3a'],
                'min_secs': 60,
                'max_secs': None,
                'min_delta': 0.0
            },
            {
                'groups': ['reversal_0_0'],
                'types': ['init3b'],
                'min_secs': 0,
                'max_secs': None,
                'min_delta': 0.0
            },
        ],
        'conditions': [
            [
                ('ma_crossover', 3, 0),
            ],
        ]
    },

    'reversal0cancel1': {
        'type': 'cancel1',
        'groups': ['reversal_0_0', 'reversal_0_1', 'reversal_0_2', 'reversal_0_bottom', 'reversal_0_top'],
        'action': 'none',
        'time_frame_max': 1800,
        'value_range_max': None,
        'follow_all': [
            {
                'groups': ['reversal_0_bottom'],
                'types': ['init1'],
                'min_secs': 0,
                'max_secs': None,
                'max_delta': 0.125
            },
            {
                'groups': ['reversal_0_0'],
                'types': ['init3b'],
                'min_secs': 0,
                'max_secs': None,
                'min_delta': 0.0
            },
        ],
        'conditions': [
            [
                ('ma_crossover', 3, 0),
            ],
        ]
    },

    'reversal0cancel1a': {
        'type': 'cancel1a',
        'groups': ['reversal_0_0', 'reversal_0_1', 'reversal_0_2', 'reversal_0_bottom', 'reversal_0_top'],
        'action': 'none',
        'time_frame_max': 1800,
        'value_range_max': None,
        'follow_all': [
            {
                'groups': ['reversal_0_bottom'],
                'types': ['init1'],
                'min_secs': 0,
                'max_secs': None,
                'min_delta': 0.3
            },
            {
                'groups': ['reversal_0_0'],
                'types': ['init3b'],
                'min_secs': 0,
                'max_secs': None,
                'min_delta': 0.0
            },
        ],
        'conditions': [
            [
                ('ma_crossover', 3, 0),
            ],
        ]
    },

    'reversal0init4': {
        'type': 'init4',
        'groups': ['reversal_0_0'],
        'action': 'none',
        'time_frame_max': 1800,
        'value_range_max': None,
        'follow_all': [
            {
                'groups': ['reversal_0_2'],
                'types': ['init2'],
                'min_secs': 0,
                'max_secs': 60 * 60 * 16
            },
            {
                'groups': ['reversal_0_0'],
                'types': ['init3b'],
                'min_secs': 0,
                'max_secs': None,
            }
        ],
        'conditions': [
            [
                ('ma_position', 5, 3),
                ('ma_position', 3, 6),
                ('ma_crossover', 0, 1),
            ],
        ]
    },

    'reversal0init5': {
        'type': 'init5',
        'groups': ['reversal_0_0'],
        'action': 'none',
        'time_frame_max': 1800,
        'value_range_max': None,
        'follow': [
            {
                'groups': ['reversal_0_0'],
                'types': ['init4'],
                'min_secs': 0,
                'max_secs': None
            },
        ],
        'conditions': [
            [
                ('ma_position', 5, 3),
                ('ma_position', 3, 6),
                ('ma_crossover', 0, 2),
            ],
        ]
    },

    'reversal0cancel3': {
        'type': 'cancel3',
        'groups': ['reversal_0_0', 'reversal_0_1', 'reversal_0_2', 'reversal_0_bottom', 'reversal_0_top'],
        'action': 'none',
        'time_frame_max': 1800,
        'value_range_max': None,
        'follow_all': [
            {
                'groups': ['reversal_0_top'],
                'types': ['init3b'],
                'min_secs': 0,
                'max_secs': None,
                'min_delta': -0.035
            },
            {
                'groups': ['reversal_0_0'],
                'types': ['init5'],
                'min_secs': 0,
                'max_secs': None
            }
        ],
        'conditions': [
            [
                ('ma_position', 5, 3),
                ('ma_position', 3, 6),
                ('ma_crossover', 0, 3),
            ],
        ]
    },

    'reversal0confirm0': {
        'type': 'confirm0',
        'groups': ['reversal_0_0', 'reversal_0_1', 'reversal_0_2', 'reversal_0_bottom', 'reversal_0_top'],
        'action': 'buy',
        'occurrence': 1,
        'time_frame_max': 1800,
        'value_range_max': None,
        'rebuy': False,
        'overlap': None,
        'push_max': 2,
        'soft_max': 1,
        'deferred_push': False,
        'push_target': 0.15,
        'stop_percent': 0.35,
        'stop_cutoff': 0.035,
        'follow': [
            {
                'groups': ['reversal_0_0'],
                'types': ['init5'],
                'min_secs': 0,
                'max_secs': None
            },
        ],
        'conditions': [
            [
                ('ma_position', 5, 3),
                ('ma_position', 3, 6),
                ('ma_crossover', 0, 3),
            ],
        ]
    },
}

# Buy detection that catches reversals after a bottom / top pattern ('pit' pattern variant)
BUY_REVERSAL_1 = {
    'reversal1init0': {
        'type': 'init0',
        'groups': ['reversal_1_0', 'reversal_1_1'],
        'action': 'none',
        'time_frame_max': 1800,
        'value_range_max': None,
        'conditions': [
            [
                ('ma_crossover', 6, 3),
                ('ma_position', 3, 2),
                ('ma_position', 3, 1),
                ('ma_position', 3, 0),
            ],
        ]
    },

    'reversal1init1': {
        'type': 'init1',
        'groups': ['reversal_1_0', 'reversal_1_bottom'],
        'action': 'none',
        'time_frame_max': 1800,
        'value_range_max': None,
        'follow': [
            {
                'groups': ['reversal_1_0'],
                'types': ['init0'],
                'min_secs': 0,
                'max_secs': None
            },
            {
                'groups': ['reversal_1_0'],
                'types': ['init1'],
                'min_secs': 0,
                'max_secs': None,
                'max_delta': 0.0
            }
        ],
        'conditions': [
            [
                ('ma_position', 5, 4),
                ('ma_position', 4, 3),
                ('ma_crossover', 0, 3),
            ],
        ]
    },

    'reversal1cancel0': {
        'type': 'cancel0',
        'groups': ['reversal_1_0', 'reversal_1_1'],
        'action': 'none',
        'time_frame_max': 1800,
        'value_range_max': None,
        'follow': [
            {
                'groups': ['reversal_1_1'],
                'types': ['init0'],
                'min_secs': 60,
                'max_secs': 60 * 60 * 8,
            },
        ],
        'conditions': [
            [
                ('ma_crossover', 3, 6),
            ],
        ]
    },

    'reversal1init2': {
        'type': 'init2',
        'groups': ['reversal_1_2', 'reversal_1_3'],
        'action': 'none',
        'time_frame_max': 1800,
        'value_range_max': None,
        'follow': [
            {
                'groups': ['reversal_1_0'],
                'types': ['init1'],
                'min_secs': 0,
                'max_secs': None,
            },
        ],
        'conditions': [
            [
                ('ma_crossover', 3, 6),
                ('ma_position', 0, 3),
                ('ma_position', 1, 5),
                ('ma_position', 2, 3),
            ],
        ]
    },

    'reversal1init3': {
        'type': 'init3',
        'groups': ['reversal_1_2', 'reversal_1_top'],
        'action': 'none',
        'time_frame_max': 1800,
        'value_range_max': None,
        'follow': [
            {
                'groups': ['reversal_1_2'],
                'types': ['init2'],
                'min_secs': 0,
                'max_secs': None
            },
            {
                'groups': ['reversal_1_2'],
                'types': ['init3'],
                'min_secs': 0,
                'max_secs': None,
                'min_delta': 0.0
            },
        ],
        'conditions': [
            [
                ('ma_crossover', 3, 0),
                ('ma_position', 3, 4),
                ('ma_position', 4, 5),
            ],
        ]
    },

    'reversal1cancel1': {
        'type': 'cancel1',
        'groups': ['reversal_1_0', 'reversal_1_1', 'reversal_1_2', 'reversal_1_3',
                   'reversal_1_bottom', 'reversal_1_top'],
        'action': 'none',
        'time_frame_max': 1800,
        'value_range_max': None,
        'follow_all': [
            {
                'groups': ['reversal_1_bottom'],
                'types': ['init1'],
                'min_secs': 0,
                'max_secs': None,
                'max_delta': 0.035
            },
            {
                'groups': ['reversal_1_2'],
                'types': ['init3'],
                'min_secs': 0,
                'max_secs': None,
                'min_delta': 0.0
            },
        ],
        'conditions': [
            [
                ('ma_crossover', 3, 0),
                ('ma_position', 3, 4),
                ('ma_position', 4, 5),
            ],
        ]
    },

    'reversal1cancel1a': {
        'type': 'cancel1a',
        'groups': ['reversal_1_0', 'reversal_1_1', 'reversal_1_2', 'reversal_1_3',
                   'reversal_1_bottom', 'reversal_1_top'],
        'action': 'none',
        'time_frame_max': 1800,
        'value_range_max': None,
        'follow_all': [
            {
                'groups': ['reversal_1_bottom'],
                'types': ['init1'],
                'min_secs': 0,
                'max_secs': None,
                'min_delta': 0.35  # 0.5
            },
            {
                'groups': ['reversal_1_2'],
                'types': ['init3'],
                'min_secs': 0,
                'max_secs': None,
                'min_delta': 0.0
            },
        ],
        'conditions': [
            [
                ('ma_crossover', 3, 0),
                ('ma_position', 3, 4),
                ('ma_position', 4, 5),
            ],
        ]
    },

    'reversal1init4': {
        'type': 'init4',
        'groups': ['reversal_1_2', 'reversal_1_pit'],
        'action': 'none',
        'time_frame_max': 1800,
        'value_range_max': None,
        'follow': [
            {
                'groups': ['reversal_1_2'],
                'types': ['init3'],
                'min_secs': 0,
                'max_secs': None
            }
        ],
        'conditions': [
            [
                ('ma_crossover', 6, 2),
                ('ma_position', 5, 6),
                ('ma_position', 2, 1),
                ('ma_position', 2, 0),
            ],
        ]
    },

    'reversal1init5': {
        'type': 'init5',
        'groups': ['reversal_1_2', 'reversal_1_pit_bottom'],
        'action': 'none',
        'time_frame_max': 1800,
        'value_range_max': None,
        'follow': [
            {
                'groups': ['reversal_1_2'],
                'types': ['init4'],
                'min_secs': 0,
                'max_secs': None
            },
            {
                'groups': ['reversal_1_2'],
                'types': ['init5'],
                'min_secs': 0,
                'max_secs': None,
                'max_delta': 0
            },
        ],
        'conditions': [
            [
                ('ma_position', 5, 6),
                ('ma_crossover', 0, 3),
            ],
        ]
    },

    'reversal1cancel2': {
        'type': 'cancel2',
        'groups': ['reversal_1_2', 'reversal_1_3', 'reversal_1_top'],
        'action': 'none',
        'time_frame_max': 1800,
        'value_range_max': None,
        'follow_all': [
            {
                'groups': ['reversal_1_top'],
                'types': ['init3'],
                'min_secs': 0,
                'max_secs': None,
                'min_delta': 0.015
            },
            {
                'groups': ['reversal_1_2'],
                'types': ['init5'],
                'min_secs': 0,
                'max_secs': None
            },
        ],
        'conditions': [
            [
                ('ma_position', 5, 6),
                ('ma_crossover', 0, 3),
            ],
        ]
    },

    'reversal1cancel3': {
        'type': 'cancel3',
        'groups': ['reversal_1_2', 'reversal_1_3', 'reversal_1_top'],
        'action': 'none',
        'time_frame_max': 1800,
        'value_range_max': None,
        'follow': [
            {
                'groups': ['reversal_1_2'],
                'types': ['init5'],
                'min_secs': 0,
                'max_secs': None
            },
        ],
        'conditions': [
            [
                ('ma_crossover', 4, 2),
            ],
        ]
    },

    'reversal1init6': {
        'type': 'init6',
        'groups': ['reversal_1_2'],
        'action': 'none',
        'time_frame_max': 1800,
        'value_range_max': None,
        'follow': [
            {
                'groups': ['reversal_1_2'],
                'types': ['init5'],
                'min_secs': 0,
                'max_secs': None
            },
        ],
        'conditions': [
            [
                ('ma_position', 5, 6),
                ('ma_slope_max', 4, 0.0),
                ('ma_crossover', 0, 4),
            ],
        ]
    },

    'reversal1init7': {
        'type': 'init7',
        'groups': ['reversal_1_2'],
        'action': 'none',
        'time_frame_max': 1800,
        'value_range_max': None,
        'follow_all': [
            {
                'groups': ['reversal_1_pit'],
                'types': ['init4'],
                'min_secs': 0,
                'max_secs': None  # 60 * 60 * 8
            },
            {
                'groups': ['reversal_1_2'],
                'types': ['init6'],
                'min_secs': 0,
                'max_secs': None
            },
        ],
        'conditions': [
            [
                ('ma_position', 5, 6),
                ('ma_slope_max', 6, 0.0),
                ('ma_crossover', 0, 6),
            ],
        ]
    },

    'reversal1confirm0': {
        'type': 'confirm0',
        'groups': ['reversal_1_2', 'reversal_1_3', 'reversal_1_top', 'reversal_1_pit', 'reversal_1_pit_bottom'],
        'action': 'buy',
        'occurrence': 1,
        'time_frame_max': 1800,
        'value_range_max': None,
        'rebuy': False,
        'overlap': None,
        'push_max': 2,
        'soft_max': 1,
        'deferred_push': False,
        'push_target': 0.115,  # Try lower / hard stop for price spike
        'stop_percent': 0.15,
        'stop_cutoff': 0.035,
        'follow': [
            {
                'groups': ['reversal_1_2'],
                'types': ['init7'],
                'min_secs': 0.0,
                'max_secs': None,
            },
        ],
        'conditions': [
            [
                ('ma_position', 5, 6),
                ('ma_slope_max', 5, 0.0),
                ('ma_crossover', 0, 5),
            ],
        ]
    },
}

# Buy detection that catches reversals after an extended decline.
BUY_REVERSAL_3 = {
    'reversal3init0': {
        'type': 'init0',
        'groups': ['reversal_3_0', 'reversal_3_1'],
        'action': 'none',
        'time_frame_max': 1800,
        'value_range_max': None,
        'conditions': [
            [
                ('ma_crossover', 6, 3),
                ('ma_position', 3, 2),
                ('ma_position', 3, 1),
                ('ma_position', 3, 0),
            ],
        ]
    },

    'reversal3init1': {
        'type': 'init1',
        'groups': ['reversal_3_1'],
        'action': 'none',
        'time_frame_max': 1800,
        'value_range_max': None,
        'follow': [
            {
                'groups': ['reversal_3_0'],
                'types': ['init0'],
                'min_secs': 0,
                'max_secs': None,
                'max_delta': -0.85
            },
        ],
        'conditions': [
            [
                ('ma_crossover', 0, 3),
            ],
        ]
    },

    'reversal3init1a': {
        'type': 'init1a',
        'groups': ['reversal_3_1'],
        'action': 'none',
        'time_frame_max': 1800,
        'value_range_max': None,
        'follow': [
            {
                'groups': ['reversal_3_1'],
                'types': ['init1'],
                'min_secs': 0,
                'max_secs': None,
            },
            {
                'groups': ['reversal_3_1'],
                'types': ['init1a'],
                'min_secs': 0,
                'max_secs': None,
                'max_delta': 0.0
            }
        ],
        'conditions': [
            [
                ('ma_crossover', 0, 3),
            ],
        ]
    },

    'reversal3cancel0': {
        'type': 'cancel0',
        'groups': ['reversal_3_0', 'reversal_3_1'],
        'action': 'none',
        'time_frame_max': 1800,
        'value_range_max': None,
        'follow': [
            {
                'groups': ['reversal_3_0'],
                'types': ['init0'],
                'min_secs': 60,
                'max_secs': 60 * 60 * 8,
            },
        ],
        'conditions': [
            [
                ('ma_crossover', 3, 6),
            ],
        ]
    },

    'reversal3confirm0': {
        'type': 'confirm0',
        'groups': ['reversal_3_0', 'reversal_3_1'],
        'action': 'buy',
        'occurrence': 1,
        'time_frame_max': 1800,
        'value_range_max': None,
        'rebuy': False,
        'overlap': None,
        'push_max': 2,
        'soft_max': 1,
        'deferred_push': False,
        'push_target': 0.06,
        'stop_percent': 0.25,
        'stop_cutoff': 0.035,
        'follow': [
            {
                'groups': ['reversal_3_1'],
                'types': ['init1a'],
                'min_secs': 0,
                'max_secs': None,
            },
        ],
        'conditions': [
            [
                ('ma_crossover', 0, 6),
            ],
        ]
    },
}

# Special detection that occurs after other buy confirmations, or after itself. It indicates when the trend following
# another detection is continuing, but has a chance of being the end-signal in an uptrend. Used for holds and re-buys.
CONTINUATIONS = {
    'continuation0confirm0': {
        'type': 'confirm',
        'action': 'holdbuy',
        'groups': ['continuation_0'],
        'sound': 'continuation.wav',
        'snapshot': False,
        'time_frame_max': 1800,
        'value_range_max': None,
        'follow': [
            {
                'groups': ['retracement_0_0', 'retracement_1_0', 'retracement_2_0', 'reversal_0_0', 'reversal_0_1', 'reversal_2_0', 'reversal_3_0',
                           'continuation_0', 'continuation_1'],
                'types': ['confirm'],
                'min_secs': 60.0,
                'max_secs': None,
                'min_delta': 0.0
            }
        ],
        'conditions': [
            [
                ('ma_crossover', 0, 1),
                ('ma_position', 1, 2),
                ('ma_position', 2, 3),
                ('ma_position', 3, 4),
                ('ma_slope_min', 2, 0.0),
                ('ma_slope_min', 3, 0.0),
                ('ma_slope_min', 4, 0.0)
            ],
        ]
    },

    # These are intended specifically to signal a return to a continuing uptrend after a sell trigger, to initiate
    # a re-buy.

    'continuation1init0': {
        'type': 'confirm',
        'action': 'none',
        'groups': ['continuation_1'],
        'sound': 'continuation.wav',
        'snapshot': False,
        'time_frame_max': 1800,
        'value_range_max': None,
        'follow': [
            {
                'groups': ['continuation_0', 'continuation_1', 'sellpush'],
                'types': ['confirm'],
                'min_secs': 0.0,
                'max_secs': None
            }
        ],
        'conditions': [
            [
                ('ma_crossover', 0, 1),
            ],
        ]
    },

    'continuation1cancel0': {
        'type': 'cancel',
        'action': 'none',
        'groups': ['continuation_1'],
        'sound': 'continuation.wav',
        'snapshot': False,
        'time_frame_max': 1800,
        'value_range_max': None,
        'follow': [
            {
                'groups': ['continuation_1'],
                'types': ['init'],
                'min_secs': 0.0,
                'max_secs': None
            }
        ],
        'conditions': [
            [
                ('ma_crossover', 1, 0),
            ]
        ]
    },

    'continuation1confirm0': {
        'type': 'confirm',
        'action': 'rebuy',
        'groups': ['continuation_1'],
        'sound': 'continuation.wav',
        'snapshot': False,
        'time_frame_max': 1800,
        'value_range_max': None,
        'follow': [
            {
                'groups': ['continuation_1'],
                'types': ['init'],
                'min_secs': 0.0,
                'max_secs': None
            }
        ],
        'conditions': [
            [
                ('ma_crossover', 0, 2),
            ]
        ]
    },

    # Signal to terminate chains of continuations to avoid false positives.

    'continuationTerminate0': {
        'type': 'terminate',
        'action': 'none',
        'groups': ['continuation_0', 'continuation_1'],
        'time_frame_max': 1800,
        'value_range_max': None,
        'follow': [
            {
                'groups': ['continuation_0', 'continuation_1', 'sellpush'],
                'types': ['confirm'],
                'min_secs': 0.0
            }
        ],
        'conditions': [
            [
                ('ma_crossover', 3, 0),
            ]
        ]
    },
}

# Detections used as sell push indicators. These trigger a sell if the trade price is above the push target and the
# number of detections exceeds the push threshold.
SELL_PUSHES = {
    'sellPush0': {
        'type': 'confirm',
        'groups': ['sellpush'],
        'action': 'sellpush',
        'time_frame_max': 1800,
        'value_range_max': None,
        'conditions': [
            [
                ('ma_crossover', 1, 0),
            ]
        ]
    },

    'sellPush1': {
        'type': 'confirm',
        'groups': ['sellpush'],
        'action': 'sellpush',
        'time_frame_max': 1800,
        'value_range_max': None,
        'conditions': [
            [
                ('ma_crossover', 2, 0),
            ]
        ]
    },
}

# Detections used as soft stop indicators. These move the stop target price up by a weighted percentage.
SOFT_STOPS = {
    'softStop0': {
        'type': 'confirm',
        'groups': ['softstop'],
        'action': 'softstop',
        'snapshot': False,
        'time_frame_max': 1800,
        'value_range_max': None,
        'weight': 1.0,
        'conditions': [
            [
                ('ma_crossover', 1, 0),
            ]
        ]
    },

    'softStop1': {
        'type': 'confirm',
        'groups': ['softstop'],
        'action': 'softstop',
        'snapshot': False,
        'time_frame_max': 1800,
        'value_range_max': None,
        'weight': 1.0,
        'conditions': [
            [
                ('ma_crossover', 2, 0),
            ]
        ]
    },

    'softStop2': {
        'type': 'confirm',
        'groups': ['softstop'],
        'action': 'softstop',
        'snapshot': False,
        'time_frame_max': 1800,
        'value_range_max': None,
        'weight': 1.0,
        'conditions': [
            [
                ('ma_crossover', 3, 0),
            ]
        ]
    },

    'softStop3': {
        'type': 'confirm',
        'groups': ['softstop'],
        'action': 'softstop',
        'snapshot': False,
        'time_frame_max': 1800,
        'value_range_max': None,
        'weight': 1.0,
        'conditions': [
            [
                ('ma_crossover', 4, 0),
            ]
        ]
    },

    'softStop4': {
        'type': 'confirm',
        'groups': ['softstop'],
        'action': 'softstop',
        'snapshot': False,
        'time_frame_max': 1800,
        'value_range_max': None,
        'weight': 1.0,
        'conditions': [
            [
                ('ma_crossover', 5, 0),
            ]
        ]
    },

    'softStop5': {
        'type': 'confirm',
        'groups': ['softstop'],
        'action': 'softstop',
        'snapshot': False,
        'time_frame_max': 1800,
        'value_range_max': None,
        'weight': 1.0,
        'conditions': [
            [
                ('ma_crossover', 6, 0),
            ]
        ]
    },
}
