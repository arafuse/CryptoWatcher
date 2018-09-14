# -*- coding: utf-8 -*-

# Copyright (c) A 2017 Adam M. Rafuse - All Rights Reserved
# Unauthorized copying of this file, via any medium is strictly prohibited
# Proprietary and confidential

"""
Archived detection definitions.
"""

__author__ = 'Adam Rafuse <$(echo nqnz.enshfr#tznvy.pbz | tr a-z# n-za-m@)>'

# Buy detection that catches reversals after a bottom / top pattern (variant).
BUY_REVERSAL_2 = {
    'reversal2init0': {
        'type': 'init0',
        'groups': ['reversal_2_0', 'reversal_2_1'],
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

    'reversal2init1': {
        'type': 'init1',
        'groups': ['reversal_2_0', 'reversal_2_bottom'],
        'action': 'none',
        'time_frame_max': 1800,
        'value_range_max': None,
        'follow': [
            {
                'groups': ['reversal_2_0'],
                'types': ['init0'],
                'min_secs': 0,
                'max_secs': None
            },
            {
                'groups': ['reversal_2_0'],
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

    'reversal2cancel0': {
        'type': 'cancel0',
        'groups': ['reversal_2_0', 'reversal_2_1'],
        'action': 'none',
        'time_frame_max': 1800,
        'value_range_max': None,
        'follow': [
            {
                'groups': ['reversal_2_1'],
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

    'reversal2cancel0a': {
        'type': 'cancel0a',
        'groups': ['reversal_2_0', 'reversal_2_1'],
        'action': 'none',
        'time_frame_max': 1800,
        'value_range_max': None,
        'follow_all': [
            {
                'groups': ['reversal_2_1'],
                'types': ['init0'],
                'min_secs': 0,
                'max_secs': None,
                'max_delta': -0.35,
            },
            {
                'groups': ['reversal_2_0'],
                'types': ['init1'],
                'min_secs': 0,
                'max_secs': None,

            },
        ],
        'conditions': [
            [
                ('ma_position', 5, 4),
                ('ma_position', 4, 3),
                ('ma_crossover', 0, 3),
            ],
        ]
    },

    'reversal2init2': {
        'type': 'init2',
        'groups': ['reversal_2_2', 'reversal_2_3'],
        'action': 'none',
        'time_frame_max': 1800,
        'value_range_max': None,
        'follow': [
            {
                'groups': ['reversal_2_0'],
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

    'reversal2init3': {
        'type': 'init3',
        'groups': ['reversal_2_2'],
        'action': 'none',
        'time_frame_max': 1800,
        'value_range_max': None,
        'follow': [
            {
                'groups': ['reversal_2_2'],
                'types': ['init2'],
                'min_secs': 0,
                'max_secs': None
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

    'reversal2init3a': {
        'type': 'init3a',
        'groups': ['reversal_2_2'],
        'action': 'none',
        'time_frame_max': 1800,
        'value_range_max': None,
        'follow': [
            {
                'groups': ['reversal_2_2'],
                'types': ['init3'],
                'min_secs': 60,
                'max_secs': None,
                'min_delta': 0.0,
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

    'reversal2init3b': {
        'type': 'init3b',
        'groups': ['reversal_2_2', 'reversal_2_top'],
        'action': 'none',
        'time_frame_max': 1800,
        'value_range_max': None,
        'follow': [
            {
                'groups': ['reversal_2_2'],
                'types': ['init3a'],
                'min_secs': 60,
                'max_secs': None,
                'min_delta': 0.0
            },
            {
                'groups': ['reversal_2_2'],
                'types': ['init3b'],
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

    'reversal2cancel1': {
        'type': 'cancel1',
        'groups': ['reversal_2_0', 'reversal_2_1', 'reversal_2_2', 'reversal_2_3',
                   'reversal_2_bottom', 'reversal_2_top'],
        'action': 'none',
        'time_frame_max': 1800,
        'value_range_max': None,
        'follow_all': [
            {
                'groups': ['reversal_2_bottom'],
                'types': ['init1'],
                'min_secs': 0,
                'max_secs': None,
                'max_delta': 0.15
            },
            {
                'groups': ['reversal_2_2'],
                'types': ['init3b'],
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

    'reversal2cancel1a': {
        'type': 'cancel1a',
        'groups': ['reversal_2_0', 'reversal_2_1', 'reversal_2_2', 'reversal_2_3',
                   'reversal_2_bottom', 'reversal_2_top'],
        'action': 'none',
        'time_frame_max': 1800,
        'value_range_max': None,
        'follow_all': [
            {
                'groups': ['reversal_2_bottom'],
                'types': ['init1'],
                'min_secs': 0,
                'max_secs': None,
                'min_delta': 0.35
            },
            {
                'groups': ['reversal_2_2'],
                'types': ['init3b'],
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

    'reversal2init4': {
        'type': 'init4',
        'groups': ['reversal_2_2', 'reversal_2_3'],
        'action': 'none',
        'time_frame_max': 1800,
        'value_range_max': None,
        'follow_all': [
            {
                'groups': ['reversal_2_3'],
                'types': ['init2'],
                'min_secs': 60 * 60 * 8,
                'max_secs': 60 * 60 * 48
            },
            {
                'groups': ['reversal_2_2'],
                'types': ['init3b'],
                'min_secs': 0,
                'max_secs': None
            }
        ],
        'conditions': [
            [
                ('ma_crossover', 6, 3),
                ('ma_position', 3, 2),
                ('ma_position', 3, 1),
                ('ma_position', 3, 0),
            ],
        ]
    },

    'reversal2cancel2': {
        'type': 'cancel2',
        'groups': ['reversal_2_2', 'reversal_2_3'],
        'action': 'none',
        'time_frame_max': 1800,
        'value_range_max': None,
        'follow_all': [
            {
                'groups': ['reversal_2_top'],
                'types': ['init3b'],
                'min_secs': 0,
                'max_secs': None,
                'min_delta': -0.035
            },
            {
                'groups': ['reversal_2_2'],
                'types': ['init4'],
                'min_secs': 0,
                'max_secs': None,
                'min_delta': 0.0
            },
        ],
        'conditions': [
            [
                ('ma_crossover', 0, 3),
            ],
        ]
    },

    'reversal2cancel2a': {
        'type': 'cancel2a',
        'groups': ['reversal_2_2', 'reversal_2_3'],
        'action': 'none',
        'time_frame_max': 1800,
        'value_range_max': None,
        'follow_all': [
            {
                'groups': ['reversal_2_top'],
                'types': ['init3b'],
                'min_secs': 0,
                'max_secs': None,
                'max_delta': -0.135
            },
            {
                'groups': ['reversal_2_2'],
                'types': ['init4'],
                'min_secs': 0,
                'max_secs': None,
                'min_delta': 0.0
            },
        ],
        'conditions': [
            [
                ('ma_crossover', 0, 3),
            ],
        ]
    },

    'reversal2confirm0': {
        'type': 'confirm0',
        'groups': ['reversal_2_2', 'reversal_2_3'],
        'action': 'buy',
        'occurrence': 1,
        'time_frame_max': 1800,
        'value_range_max': None,
        'rebuy': False,
        'overlap': None,
        'push_max': 2,
        'soft_max': 1,
        'deferred_push': False,
        'push_target': 0.1,
        'stop_percent': 0.25,
        'stop_cutoff': 0.035,
        'follow_all': [
            {
                'groups': ['reversal_2_top'],
                'types': ['init3b'],
                'min_secs': 0,
                'max_secs': None,
                'min_delta': -0.135
            },
            {
                'groups': ['reversal_2_2'],
                'types': ['init4'],
                'min_secs': 0,
                'max_secs': None,
            }
        ],
        'conditions': [
            [
                ('ma_crossover', 0, 3),
            ],
        ]
    },
}

# Sell push modifiers (archived).
SELL_PUSHES = {
    'pushRelease0': {
        'type': 'confirm',
        'groups': ['pushrelease'],
        'action': 'pushrelease',
        'time_frame_max': 1800,
        'value_range_max': None,
        'conditions': [
            [
                ('vdma_xcrossover', 0, False),
            ]
        ]
    },
}

# Detections used as hard stop indicators for specific detection types.
# TODO: "Spike-catcher" detection (cross after very steep upward slope)
HARD_STOPS = {
    'hardStop0init0': {
        'type': 'init0',
        'groups': ['hardstop_0'],
        'action': 'none',
        'value_range_max': None,
        'follow': [
            {
                'groups': ['retracement_0_0'],
                'types': ['confirm0'],
                'min_secs': 60,
                'max_secs': None
            }
        ],
        'conditions': [
            [
                ('ma_crossover', 6, 0),
            ],
        ]
    },

    'hardStop1confirm0': {
        'type': 'confirm',
        'groups': ['hardstop_0'],
        'action': 'hardstop',
        'threshold': 1,
        'value_range_max': None,
        'apply': {
            'groups': ['retracement_0_0']
        },
        'follow': [
            {
                'groups': ['hardstop_0'],
                'types': ['init0'],
                'min_secs': 0,
                'max_secs': None
            }
        ],
        'conditions': [
            [
                ('ma_crossover', 6, 1),
            ],
        ]
    },
}

# Signals used as soft sell indicators. These trigger a sell if the trade is above the soft target (deprecated)
SOFT_SELLS = {
    'softSell0': {
        'type': 'confirm',
        'groups': ['softsell'],
        'action': 'softsell',
        'time_frame_max': 1800,
        'value_range_max': None,
        'conditions': [
            [
                ('ma_crossover', 3, 0),
            ]
        ]
    },
}

# Signals used as hard sell indicators. These trigger a sell if the trade is above the hard target (deprecated).
HARD_SELLS = {
    'hardSell0': {
        'type': 'confirm',
        'groups': ['hardsell'],
        'action': 'hardsell',
        'time_frame_max': 1800,
        'value_range_max': None,
        'conditions': [
            [
                ('ma_crossover', 4, 0),
            ]
        ]
    },

    'hardSell1': {
        'type': 'confirm',
        'groups': ['hardsell'],
        'action': 'hardsell',
        'time_frame_max': 1800,
        'value_range_max': None,
        'apply': {
            'groups': ['default']
        },
        'conditions': [
            [
                ('ma_crossover', 5, 0),
            ]
        ]
    },

    'hardSell2': {
        'type': 'confirm',
        'groups': ['hardsell'],
        'action': 'hardsell',
        'time_frame_max': 1800,
        'value_range_max': None,
        'apply': {
            'groups': ['default']
        },
        'conditions': [
            [
                ('ma_crossover', 6, 0),
            ]
        ]
    },
}
