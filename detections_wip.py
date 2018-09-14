# -*- coding: utf-8 -*-

# Copyright (c) A 2017 Adam M. Rafuse - All Rights Reserved
# Unauthorized copying of this file, via any medium is strictly prohibited
# Proprietary and confidential

"""
Work-in-progess detection definitions.
"""

__author__ = 'Adam Rafuse <$(echo nqnz.enshfr#tznvy.pbz | tr a-z# n-za-m@)>'

# Detection for scanning breakout patterns.
BUY_BREAKOUT_0_SCAN_0 = {
    'breakout0init0': {
        'type': 'init0',
        'groups': ['breakout_0_0'],
        'action': 'none',
        'time_frame_max': 1800,
        'value_range_max': None,
        'conditions': [
            [
                ('ma_crossover', 0, 1),
            ],
        ]
    },

    'breakout0init1': {
        'type': 'init1',
        'groups': ['breakout_0_1'],
        'action': 'none',
        'time_frame_max': 1800,
        'value_range_max': None,
        'follow': [
            {
                'groups': ['breakout_0_0'],
                'types': ['init0'],
                'min_secs': 0,
                'max_secs': None
            }
        ],
        'conditions': [
            [
                ('ma_crossover', 0, 2),
            ],
        ]
    },

    'breakout0init2': {
        'type': 'init2',
        'groups': ['breakout_0_2'],
        'action': 'none',
        'time_frame_max': 1800,
        'value_range_max': None,
        'follow': [
            {
                'groups': ['breakout_0_1'],
                'types': ['init1'],
                'min_secs': 0,
                'max_secs': None
            }
        ],
        'conditions': [
            [
                ('ma_crossover', 0, 3),
            ],
        ]
    },

    'breakout0confirm0': {
        'type': 'confirm',
        'groups': ['breakout_0_0', 'breakout_0_1', 'breakout_0_2'],
        'action': 'buy',
        'occurrence': 1,
        'time_frame_max': 1800,
        'value_range_max': 0.01,
        'rebuy': False,
        'overlap': 5.0,
        'push_max': 2,
        'soft_max': 1,
        'deferred_push': False,
        'push_target': 0.08,
        'stop_percent': 0.15,
        'stop_cutoff': 0.035,
        'follow': [
            {
                'groups': ['breakout_0_2'],
                'types': ['init2'],
                'min_secs': 0,
                'max_secs': 60 * 60 * 8,
                'min_delta': 0.15
            }
        ],
        'conditions': [
            [
                ('ma_position', 0, 6),
            ],
        ]
    },
}

# Detection for scanning breakout patterns.
BUY_BREAKOUT_0_SCAN_1 = {
    'breakout0init0': {
        'type': 'init0',
        'groups': ['breakout_0_0'],
        'action': 'none',
        'time_frame_max': 1800,
        'value_range_max': None,
        'conditions': [
            [
                ('ma_crossover', 4, 3),
            ],
        ]
    },

    'breakout0confirm0': {
        'type': 'confirm',
        'groups': ['breakout_0_0'],
        'action': 'buy',
        'occurrence': 1,
        'time_frame_min': 900,
        'time_frame_max': 1800,
        'value_range_max': 0.015,
        'rebuy': False,
        'overlap': None,
        'push_max': 2,
        'soft_max': 1,
        'deferred_push': False,
        'push_target': 0.02,
        'stop_percent': 0.25,
        'stop_cutoff': 0.035,
        'follow': [
            {
                'groups': ['breakout_0_0'],
                'types': ['init0'],
                'min_secs': 60 * 240,
                'max_secs': 60 * 960,
                'max_delta': -0.065,
                'min_delta': -0.135,
            }
        ],
        'conditions': [
            [
                ('ma_crossover', 0, 1),
            ],
            [
                ('ma_crossover', 0, 2),
            ],
            [
                ('ma_crossover', 0, 3),
            ],
            [
                ('ma_crossover', 0, 4),
            ],
        ]
    },
}

# Buy detection that catches dips.
BUY_RETRACEMENT_3 = {
    'retracement3init0': {
        'type': 'init0',
        'groups': ['retracement_3_0'],
        'action': 'none',
        'time_frame_max': 1800,
        'value_range_max': None,
        'conditions': [
            [
                ('ma_crossover', 3, 2),
            ]
        ]
    },

    'retracement3init1': {
        'type': 'init1',
        'groups': ['retracement_3_0'],
        'action': 'none',
        'time_frame_max': 1800,
        'value_range_max': None,
        'follow_all': [
            {
                'groups': ['retracement_3_0'],
                'types': ['init0'],
                'min_secs': 0,
                'max_secs': None
            }
        ],
        'conditions': [
            [                
                ('ma_slope_max', 1, -5.0),
                ('ma_crossover', 0, 1),
            ],
        ]
    },

    'retracement3confirm0': {
        'type': 'confirm0',
        'groups': ['retracement_3_0'],
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
                'groups': ['retracement_3_0'],
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

# Buy detection that works off of drops in volume differentials.
BUY_VOLDIP_0 = {
    'voldip0init0': {
        'type': 'init0',
        'groups': ['voldip_0_0'],
        'action': 'none',
        'time_frame_max': 1800,
        'value_range_max': None,
        'conditions': [
            [
                ('vdma_xcrossover', 0, False)
            ]
        ]
    },

    'voldip0confirm0': {
        'type': 'confirm0',
        'groups': ['voldip_0_0'],
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
        'stop_percent': 0.35,
        'stop_cutoff': 0.035,
        'follow': [
            {
                'groups': ['voldip_0_0'],
                'types': ['init0'],
                'min_secs': 0,
                'max_secs': None
            },
        ],
        'conditions': [
            [
                ('vdma_yposition', 0, -0.5, False)
            ],
        ]
    },
}

# Detection for scanning coil patterns.
BUY_COIL_0_SCAN_0 = {
    'coil0init0': {
        'type': 'init0',
        'groups': ['coil_0_0'],
        'action': 'none',
        'time_frame_max': 1800,
        'value_range_max': None,
        'follow': [
            {
                'groups': ['coil_0_0'],
                'types': [None, 'cancel0', 'confirm0'],
                'min_secs': 60,
                'max_secs': None
            }
        ],
        'conditions': [
            [
                ('ma_distance_max', 1, 6, 0.001),
            ],
        ]
    },

    'coil0cancel0': {
        'type': 'cancel0',
        'groups': ['coil_0_0'],
        'action': 'none',
        'time_frame_max': 1800,
        'value_range_max': None,
        'follow': [
            {
                'groups': ['coil_0_0'],
                'types': ['init0'],
                'min_secs': 60,
                'max_secs': None
            }
        ],
        'conditions': [
            [
                ('ma_distance_min', 1, 6, 0.001),
            ],
        ]
    },

    'coil0confirm0': {
        'type': 'confirm0',
        'groups': ['coil_0_0'],
        'action': 'buy',
        'occurrence': 1,
        'time_frame_max': 1800,
        'value_range_max': None,
        'rebuy': False,
        'overlap': None,
        'push_max': 2,
        'soft_max': 1,
        'deferred_push': False,
        'push_target': 0.05,
        'stop_percent': 0.15,
        'stop_cutoff': 0.035,
        'follow': [
            {
                'groups': ['coil_0_0'],
                'types': ['init0'],
                'min_secs': 60 * 60,  # increase
                'max_secs': None
            }
        ],
        'conditions': [
            [
                ('ma_distance_max', 1, 6, 0.001),
            ],
        ]
    },
}

# Detection for scanning coil patterns.
BUY_COIL_0_SCAN_1 = {
    'coil0init0': {
        'type': 'init0',
        'groups': ['coil_0_0'],
        'action': 'none',
        'time_frame_max': 1800,
        'value_range_max': None,
        'follow': [
            {
                'groups': ['coil_0_0'],
                'types': [None, 'cancel0', 'cancel1', 'cancel2', 'confirm0'],
                'min_secs': 60,
                'max_secs': None
            }
        ],
        'conditions': [
            [
                ('ma_distance_max', 1, 4, 0.001),
                ('ma_distance_max', 2, 4, 0.001),
                ('ma_distance_max', 3, 4, 0.001),
            ],
        ]
    },

    'coil0cancel0': {
        'type': 'cancel0',
        'groups': ['coil_0_0'],
        'action': 'none',
        'time_frame_max': 1800,
        'value_range_max': None,
        'follow': [
            {
                'groups': ['coil_0_0'],
                'types': ['init0'],
                'min_secs': 60,
                'max_secs': None
            }
        ],
        'conditions': [
            [
                ('ma_distance_min', 1, 4, 0.001),
            ],
        ]
    },

    'coil0cancel1': {
        'type': 'cancel1',
        'groups': ['coil_0_0'],
        'action': 'none',
        'time_frame_max': 1800,
        'value_range_max': None,
        'follow': [
            {
                'groups': ['coil_0_0'],
                'types': ['init0'],
                'min_secs': 60,
                'max_secs': None
            }
        ],
        'conditions': [
            [
                ('ma_distance_min', 2, 4, 0.001),
            ],
        ]
    },

    'coil0cancel2': {
        'type': 'cancel2',
        'groups': ['coil_0_0'],
        'action': 'none',
        'time_frame_max': 1800,
        'value_range_max': None,
        'follow': [
            {
                'groups': ['coil_0_0'],
                'types': ['init0'],
                'min_secs': 60,
                'max_secs': None
            }
        ],
        'conditions': [
            [
                ('ma_distance_min', 3, 4, 0.001),
            ],
        ]
    },

    # TODO: Try 1,2,3 under 5 (one variant)
    # TODO: Try 1,2,3 under 6 (one variant)
    # TODO: Try 4,5,6 stack, +slopes (one variant)

    'coil0confirm0': {
        'type': 'confirm0',
        'groups': ['coil_0_0'],
        'action': 'buy',
        'occurrence': 1,
        'time_frame_max': 1800,
        'value_range_max': None,
        'rebuy': False,
        'overlap': None,
        'push_max': 2,
        'soft_max': 1,
        'deferred_push': False,
        'push_target': 0.05,
        'stop_percent': 0.15,
        'stop_cutoff': 0.035,
        'follow': [
            {
                'groups': ['coil_0_0'],
                'types': ['init0'],
                'min_secs': 60 * 60,
                'max_secs': None,
                'min_delta': -0.001,
                'max_delta': 0.001,
            }
        ],
        'conditions': [
            [
                ('ma_distance_max', 1, 4, 0.001),
                ('ma_distance_max', 2, 4, 0.001),
                ('ma_distance_max', 3, 4, 0.001),
            ],
        ]
    },
}

# Detection that attempts to find the bottom of a medium-term price descent. Reference example of using 3-way split
# groups, not working for trading.
BUY_BOTTOM_0 = {
    'bottom0init0': {
        'type': 'init0',
        'groups': ['bottom_0', 'bottom_0_0'],
        'action': 'none',
        'time_frame_max': 1800,
        'value_range_max': None,
        'conditions': [
            [
                ('ma_crossover', 6, 0),
                ('ma_position', 2, 6),
                ('ma_position', 3, 6),
                ('ma_position', 4, 6),
                ('ma_position', 5, 6),
            ],
        ]
    },

    'bottom0cancel0': {
        'type': 'cancel0',
        'groups': ['bottom_0', 'bottom_0_0', 'bottom_0_1'],
        'action': 'none',
        'time_frame_max': 1800,
        'value_range_max': None,
        'follow': [
            {
                'groups': ['bottom_0_0'],
                'types': ['init0'],
                'min_secs': 60,
                'max_secs': None,
            },
        ],
        'conditions': [
            [
                ('ma_crossover', 1, 6),  # 0, 6?
            ],
        ]
    },

    'bottom0init1': {
        'type': 'init1',
        'groups': ['bottom_0_0'],
        'action': 'none',
        'time_frame_max': 1800,
        'value_range_max': None,
        'follow': [
            {
                'groups': ['bottom_0_0'],
                'types': ['init0'],
                'min_secs': 60,
                'max_secs': None
            }
        ],
        'conditions': [
            [
                ('ma_crossover', 6, 5),
                ('ma_position', 5, 4),
                ('ma_position', 5, 3),
                ('ma_position', 5, 2),
                ('ma_position', 5, 1),
                ('ma_position', 5, 0),
            ],
        ]
    },

    'bottom0cancel1': {
        'type': 'cancel1',
        'groups': ['bottom_0', 'bottom_0_0', 'bottom_0_1'],
        'action': 'none',
        'time_frame_max': 1800,
        'value_range_max': None,
        'follow_all': [
            {
                'groups': ['bottom_0'],
                'types': ['init0'],
                'min_secs': 60,
                'max_secs': None,
                'min_delta': 0.0025
            },
            {
                'groups': ['bottom_0_0'],
                'types': ['init1'],
                'min_secs': 0,
                'max_secs': None
            },
        ],
        'conditions': [
            [
                ('ma_crossover', 1, 6),
            ],
        ]
    },

    'bottom0cancel2': {
        'type': 'cancel2',
        'groups': ['bottom_0', 'bottom_0_0', 'bottom_0_1'],
        'action': 'none',
        'time_frame_max': 1800,
        'value_range_max': None,
        'follow_all': [
            {
                'groups': ['bottom_0'],
                'types': ['init0'],
                'min_secs': 60,
                'max_secs': None,
                'max_delta': -0.0025
            },
            {
                'groups': ['bottom_0_0'],
                'types': ['init1'],
                'min_secs': 0,
                'max_secs': None
            },
        ],
        'conditions': [
            [
                ('ma_crossover', 1, 6),
            ],
        ]
    },

    'bottom0confirm0': {
        'type': 'confirm0',
        'groups': ['bottom_0', 'bottom_0_0'],
        'action': 'buy',
        'occurrence': 1,
        'time_frame_max': 1800,
        'value_range_max': None,
        'rebuy': False,
        'overlap': 5.0,
        'push_max': 2,
        'soft_max': 1,
        'deferred_push': False,
        'push_target': 0.05,
        'stop_percent': 0.15,
        'stop_cutoff': 0.035,
        'follow_all': [
            {
                'groups': ['bottom_0'],
                'types': ['init0'],
                'min_secs': 0,
                'max_secs': None,
                'min_delta': -0.0025,
                'max_delta': 0.0025
            },
            {
                'groups': ['bottom_0_0'],
                'types': ['init1'],
                'min_secs': 0,
                'max_secs': None
            },
        ],
        'conditions': [
            [
                ('ma_crossover', 0, 6),
                ('ma_position', 6, 2),
                ('ma_position', 6, 3),
                ('ma_position', 6, 4),
                ('ma_position', 6, 5),
            ],
        ]
    },
}

# Buy detection that tries to catch ranging patterns (vulnerable to whipsaws).
BUY_RANGE_0 = {
    'range0init0': {
        'type': 'init0',
        'groups': ['range_0_0', 'range_0_1'],
        'action': 'none',
        'time_frame_max': 1800,
        'value_range_max': None,
        'conditions': [
            [
                ('ma_crossover', 3, 2),
            ],
        ]
    },

    'range0init1': {
        'type': 'init1',
        'groups': ['range_0_1'],
        'action': 'none',
        'time_frame_max': 1800,
        'value_range_max': None,
        'follow': [
            {
                'groups': ['range_0_0'],
                'types': ['init0'],
                'min_secs': 60,
                'max_secs': None,
                'min_delta': -0.1
            }
        ],
        'conditions': [
            [
                ('ma_crossover', 1, 2),
            ],
        ]
    },

    'range0confirm0': {
        'type': 'confirm0',
        'groups': ['range_0_0', 'range_0_1'],
        'action': 'buy',
        'occurrence': 1,
        'time_frame_max': 1800,
        'value_range_max': None,
        'rebuy': False,
        'overlap': 5.0,
        'push_max': 2,
        'soft_max': 1,
        'deferred_push': False,
        'push_target': 0.0,
        'stop_percent': 0.15,
        'stop_cutoff': 0.015,
        'follow_all': [
            {
                'groups': ['range_0_0'],
                'types': ['init0'],
                'min_secs': 60,
                'max_secs': None,
                'min_delta': -0.1
            },
            {
                'groups': ['range_0_1'],
                'types': ['init1'],
                'min_secs': 0,
                'max_secs': None,
                'min_delta': 0.0,
                'max_delta': 0.1
            }
        ],
        'conditions': [
            [
                ('ma_crossover', 2, 3),
            ],
        ]
    },

    'range0stop0init0': {
        'type': 'init0',
        'groups': ['range_0_stop_0'],
        'action': 'none',
        'value_range_max': None,
        'conditions': [
            [
                ('ma_crossover', 1, 0),
            ],
        ]
    },

    'range0stop0init1': {
        'type': 'init1',
        'groups': ['range_0_stop_0'],
        'action': 'none',
        'value_range_max': None,
        'follow': [
            {
                'groups': ['range_0_stop_0'],
                'types': ['init0'],
                'min_secs': 0,
                'max_secs': None
            }
        ],
        'conditions': [
            [
                ('ma_crossover', 2, 0),
            ],
        ]
    },

    'range0stop0confirm0': {
        'type': 'confirm',
        'groups': ['range_0_stop_0'],
        'action': 'hardstop',
        'threshold': 1,
        'value_range_max': None,
        'apply': {
            'groups': ['range_0_0']
        },
        'follow': [
            {
                'groups': ['range_0_stop_0'],
                'types': ['init1'],
                'min_secs': 0,
                'max_secs': None
            }
        ],
        'conditions': [
            [
                ('ma_crossover', 3, 0),
            ],
        ]
    },
}

# Buy detection that catches price spikes and breakouts.
BUY_SPIKE_0 = {
    'spike0init0': {
        'type': 'init0',
        'groups': ['spike_0'],
        'action': 'none',
        'time_frame_max': 1800,
        'value_range_max': None,
        'conditions': [
            [
                ('vdma_yposition', 0, -0.2, False),
            ],
        ]
    },

    'spike0confirm0': {
        'type': 'confirm0',
        'groups': ['spike_0'],
        'action': 'buy',
        'occurrence': 1,
        'time_frame_max': 1800,
        'value_range_max': None,
        'rebuy': False,
        'overlap': 5.0,
        'push_max': 2,
        'soft_max': 1,
        'deferred_push': False,
        'push_target': 0.08,
        'stop_percent': 0.15,
        'stop_cutoff': 0.035,
        'follow': [
            {
                'groups': ['spike_0'],
                'types': ['init0'],
                'min_secs': 0,
                'max_secs': 60,
            },
        ],
        'conditions': [
            [
                ('vdma_yposition', 0, 0.2, True),
            ],
        ]
    },
}

# Buy detection that catches lows above downtrends that form a 'pit' pattern (variant).
BUY_PIT_1 = {
    'pit1init0': {
        'type': 'init0',
        'groups': ['pit_1_0', 'pit_1_1', 'pit_1_2'],
        'action': 'none',
        'time_frame_max': 1800,
        'value_range_max': None,
        'conditions': [
            [
                ('ma_position', 5, 6),
                ('ma_crossover', 5, 0),
            ],
            [
                ('ma_position', 5, 6),
                ('ma_crossover', 6, 0),
            ],
        ]
    },

    'pit1init1': {
        'type': 'init1',
        'groups': ['pit_1_0', 'pit_1_1', 'pit_1_2'],
        'action': 'none',
        'time_frame_max': 1800,
        'value_range_max': None,
        'follow': [
            {
                'groups': ['pit_1_0'],
                'types': ['init0'],
                'min_secs': 0,
                'max_secs': None
            }
        ],
        'conditions': [
            [
                ('ma_position', 5, 6),
                ('ma_crossover', 5, 1),
            ],
            [
                ('ma_position', 5, 6),
                ('ma_crossover', 6, 1),
            ],
        ]
    },

    'pit1init2': {
        'type': 'init2',
        'groups': ['pit_1_0', 'pit_1_1', 'pit_1_2'],
        'action': 'none',
        'time_frame_max': 1800,
        'value_range_max': None,
        'follow': [
            {
                'groups': ['pit_1_0'],
                'types': ['init1'],
                'min_secs': 0,
                'max_secs': None
            }
        ],
        'conditions': [
            [
                ('ma_position', 5, 6),
                ('ma_crossover', 5, 2),
            ],
            [
                ('ma_position', 5, 6),
                ('ma_crossover', 6, 2),
            ],
        ]
    },

    'pit1init3': {
        'type': 'init3',
        'groups': ['pit_1_1'],
        'action': 'none',
        'time_frame_max': 1800,
        'value_range_max': None,
        'follow': [
            {
                'groups': ['pit_1_1'],
                'types': ['init2'],
                'min_secs': 0,
                'max_secs': None
            },
        ],
        'conditions': [
            [
                ('ma_crossover', 6, 5),
            ],
        ]
    },

    'pit1init4': {
        'type': 'init4',
        'groups': ['pit_1_2'],
        'action': 'none',
        'time_frame_max': 1800,
        'value_range_max': None,
        'follow': [
            {
                'groups': ['pit_1_2'],
                'types': ['init2'],
                'min_secs': 0,
                'max_secs': None
            },
        ],
        'conditions': [
            [
                ('vdma_yposition', 0, -0.3, False)
            ],
        ]
    },

    'pit1init5': {
        'type': 'init5',
        'groups': ['pit_1_0'],
        'action': 'none',
        'time_frame_max': 1800,
        'value_range_max': None,
        'follow': [
            {
                'groups': ['pit_1_0'],
                'types': ['init2'],
                'min_secs': 0,
                'max_secs': None
            },
        ],
        'conditions': [
            [
                ('ma_position', 5, 6),
                ('ma_position', 6, 1),
                ('ma_crossover', 0, 1),
            ],
        ]
    },

    'pit1init6': {
        'type': 'init6',
        'groups': ['pit_1_0'],
        'action': 'none',
        'time_frame_max': 1800,
        'value_range_max': None,
        'follow': [
            {
                'groups': ['pit_1_0'],
                'types': ['init5'],
                'min_secs': 0,
                'max_secs': None
            },
        ],
        'conditions': [
            [
                ('ma_position', 5, 6),
                ('ma_position', 6, 2),
                ('ma_crossover', 0, 2),
            ],
        ]
    },

    'pit1init7': {
        'type': 'init7',
        'groups': ['pit_1_0'],
        'action': 'none',
        'time_frame_max': 1800,
        'value_range_max': None,
        'follow': [
            {
                'groups': ['pit_1_0'],
                'types': ['init6'],
                'min_secs': 0,
                'max_secs': None
            },
        ],
        'conditions': [
            [
                ('ma_position', 5, 6),
                ('ma_position', 6, 3),
                ('ma_crossover', 0, 3),
            ],
        ]
    },

    'pit1init8': {
        'type': 'init8',
        'groups': ['pit_1_0'],
        'action': 'none',
        'time_frame_max': 1800,
        'value_range_max': None,
        'follow': [
            {
                'groups': ['pit_1_0'],
                'types': ['init7'],
                'min_secs': 0,
                'max_secs': None
            },
        ],
        'conditions': [
            [
                ('ma_position', 6, 5),
                ('ma_position', 5, 1),
                ('ma_crossover', 0, 1),
            ],
        ]
    },

    'pit1init9': {
        'type': 'init9',
        'groups': ['pit_1_0'],
        'action': 'none',
        'time_frame_max': 1800,
        'value_range_max': None,
        'follow': [
            {
                'groups': ['pit_1_0'],
                'types': ['init8'],
                'min_secs': 0,
                'max_secs': None
            },
        ],
        'conditions': [
            [
                ('ma_position', 6, 5),
                ('ma_position', 5, 2),
                ('ma_crossover', 0, 2),
            ],
        ]
    },

    'pit1init10': {
        'type': 'init10',
        'groups': ['pit_1_0'],
        'action': 'none',
        'time_frame_max': 1800,
        'value_range_max': None,
        'follow': [
            {
                'groups': ['pit_1_0'],
                'types': ['init9'],
                'min_secs': 0,
                'max_secs': None
            },
        ],
        'conditions': [
            [
                ('ma_position', 6, 5),
                ('ma_position', 5, 3),
                ('ma_crossover', 0, 3),
            ],
        ]
    },

    'pit1init11': {
        'type': 'init11',
        'groups': ['pit_1_0'],
        'action': 'none',
        'time_frame_max': 1800,
        'value_range_max': None,
        'follow': [
            {
                'groups': ['pit_1_0'],
                'types': ['init10'],
                'min_secs': 0,
                'max_secs': None
            },
        ],
        'conditions': [
            [
                ('ma_position', 6, 5),
                ('ma_crossover', 0, 4),
                ('ma_position', 5, 4),
                ('ma_slope_max', 4, 0.0),
            ],
        ]
    },

    'pit1cancel0': {
        'type': 'cancel0',
        'groups': ['pit_1_0', 'pit_1_1', 'pit_1_2'],
        'action': 'none',
        'time_frame_max': 1800,
        'value_range_max': None,
        'follow': [
            {
                'groups': ['pit_1_0'],
                'types': ['init0', 'init1', 'init2', 'init3', 'init4', 'init5', 'init6', 'init7',
                          'init8', 'init9', 'init10', 'init11'],
                'min_secs': 0,
                'max_secs': None
            },
        ],
        'conditions': [
            [
                ('ma_crossover', 2, 6),
            ],
        ]
    },

    'pit1cancel1': {
        'type': 'cancel1',
        'groups': ['pit_1_0', 'pit_1_1', 'pit_1_2'],
        'action': 'none',
        'time_frame_max': 1800,
        'value_range_max': None,
        'follow': [
            {
                'groups': ['pit_1_0'],
                'types': ['init0', 'init1', 'init2', 'init3', 'init4', 'init5', 'init6', 'init7',
                          'init8', 'init9', 'init10', 'init11'],
                'min_secs': 0,
                'max_secs': None
            },
        ],
        'conditions': [
            [
                ('ma_crossover', 2, 5),
            ],
        ]
    },

    'pit1cancel2': {
        'type': 'cancel2',
        'groups': ['pit_1_0', 'pit_1_1', 'pit_1_2'],
        'action': 'none',
        'time_frame_max': 1800,
        'value_range_max': None,
        'follow': [
            {
                'groups': ['pit_1_0'],
                'types': ['init0', 'init1', 'init2', 'init3', 'init4', 'init5', 'init6', 'init7'],
                'min_secs': 0,
                'max_secs': None
            },
        ],
        'conditions': [
            [
                ('ma_crossover', 2, 4),
            ],
        ]
    },

    'pit1init12': {
        'type': 'init12',
        'groups': ['pit_1_0', 'pit_1_1'],
        'action': 'none',
        'time_frame_max': 1800,
        'value_range_max': None,
        'follow_all': [
            {
                'groups': ['pit_1_0'],
                'types': ['init11'],
                'min_secs': 0,
                'max_secs': None
            },
            {
                'groups': ['pit_1_1'],
                'types': ['init3'],
                'min_secs': 0,
                'max_secs': None,
                'min_ma_delta': -0.01,
            },
            {
                'groups': ['pit_1_2'],
                'types': ['init4'],
                'min_secs': 0,
                'max_secs': None,
            },
        ],
        'conditions': [
            [
                ('ma_position', 6, 5),
                ('ma_crossover', 0, 5),
            ],
        ]
    },

    'pit1confirm0': {
        'type': 'confirm',
        'groups': ['pit_1_0', 'pit_1_1'],
        'action': 'buy',
        'occurrence': 1,
        'time_frame_max': 1800,
        'value_range_max': None,
        'rebuy': False,
        'overlap': 5.0,
        'push_max': 2,
        'soft_max': 1,
        'deferred_push': False,
        'push_target': 0.125,  # 1.5?
        'stop_percent': 0.15,
        'stop_cutoff': 0.035,
        'follow': [
            {
                'groups': ['pit_1_0'],
                'types': ['init12'],
                'min_secs': 0.0,
                'max_secs': None,
            },
        ],
        'conditions': [
            [
                ('vdma_yposition', 0, 0.0, True),
            ],
        ]
    },
}

# Buy detection that catches lows above downtrends that form a 'pit' pattern (variant).
BUY_PIT_1_ALT = {
    'pit1init0': {
        'type': 'init0',
        'groups': ['pit_1_0', 'pit_1_1'],
        'action': 'none',
        'time_frame_max': 1800,
        'value_range_max': None,
        'conditions': [
            [
                ('ma_position', 5, 6),
                ('ma_crossover', 5, 0),
            ],
            [
                ('ma_position', 5, 6),
                ('ma_crossover', 6, 0),
            ],
        ]
    },

    'pit1init1': {
        'type': 'init1',
        'groups': ['pit_1_0'],
        'action': 'none',
        'time_frame_max': 1800,
        'value_range_max': None,
        'follow': [
            {
                'groups': ['pit_1_0'],
                'types': ['init0'],
                'min_secs': 0,
                'max_secs': None
            }
        ],
        'conditions': [
            [
                ('ma_position', 5, 6),
                ('ma_crossover', 5, 1),
            ],
            [
                ('ma_position', 5, 6),
                ('ma_crossover', 6, 1),
            ],
        ]
    },

    'pit1init2': {
        'type': 'init2',
        'groups': ['pit_1_0'],
        'action': 'none',
        'time_frame_max': 1800,
        'value_range_max': None,
        'follow': [
            {
                'groups': ['pit_1_0'],
                'types': ['init1'],
                'min_secs': 0,
                'max_secs': None
            }
        ],
        'conditions': [
            [
                ('ma_position', 5, 6),
                ('ma_crossover', 5, 2),
            ],
            [
                ('ma_position', 5, 6),
                ('ma_crossover', 6, 2),
            ],
        ]
    },

    'pit1init3': {
        'type': 'init3',
        'groups': ['pit_1_0'],
        'action': 'none',
        'time_frame_max': 1800,
        'value_range_max': None,
        'follow': [
            {
                'groups': ['pit_1_0'],
                'types': ['init2'],
                'min_secs': 0,
                'max_secs': None
            }
        ],
        'conditions': [
            [
                ('ma_position', 5, 6),
                ('ma_crossover', 5, 3),
            ],
            [
                ('ma_position', 5, 6),
                ('ma_crossover', 6, 3),
            ],
        ]
    },

    'pit1init4': {
        'type': 'init4',
        'groups': ['pit_1_0'],
        'action': 'none',
        'time_frame_max': 1800,
        'value_range_max': None,
        'follow': [
            {
                'groups': ['pit_1_0'],
                'types': ['init3'],
                'min_secs': 0,
                'max_secs': None
            }
        ],
        'conditions': [
            [
                ('ma_position', 5, 6),
                ('ma_crossover', 5, 4),
            ],
            [
                ('ma_position', 5, 6),
                ('ma_crossover', 6, 4),
            ],
        ]
    },

    'pit1init5': {
        'type': 'init5',
        'groups': ['pit_1_1'],
        'action': 'none',
        'time_frame_max': 1800,
        'value_range_max': None,
        'follow': [
            {
                'groups': ['pit_1_1'],
                'types': ['init0'],
                'min_secs': 0,
                'max_secs': None
            },
        ],
        'conditions': [
            [
                ('vdma_yposition', 0, -0.3, False)
            ],
        ]
    },

    'pit1cancel0': {
        'type': 'cancel0',
        'groups': ['pit_1_0', 'pit_1_1'],
        'action': 'none',
        'time_frame_max': 1800,
        'value_range_max': None,
        'follow': [
            {
                'groups': ['pit_1_0'],
                'types': ['init0', 'init1', 'init2', 'init3', 'init4', 'init5'],
                'min_secs': 0,
                'max_secs': None
            },
        ],
        'conditions': [
            [
                ('ma_crossover', 2, 6),
            ],
        ]
    },

    'pit1cancel1': {
        'type': 'cancel1',
        'groups': ['pit_1_0', 'pit_1_1'],
        'action': 'none',
        'time_frame_max': 1800,
        'value_range_max': None,
        'follow': [
            {
                'groups': ['pit_1_0'],
                'types': ['init0', 'init1', 'init2', 'init3', 'init4', 'init5'],
                'min_secs': 0,
                'max_secs': None
            },
        ],
        'conditions': [
            [
                ('ma_crossover', 2, 5),
            ],
        ]
    },

    'pit1cancel2': {
        'type': 'cancel2',
        'groups': ['pit_1_0', 'pit_1_1'],
        'action': 'none',
        'time_frame_max': 1800,
        'value_range_max': None,
        'follow': [
            {
                'groups': ['pit_1_0'],
                'types': ['init0', 'init1', 'init2', 'init3', 'init4', 'init5'],
                'min_secs': 0,
                'max_secs': None
            },
        ],
        'conditions': [
            [
                ('ma_crossover', 2, 4),
            ],
        ]
    },

    'pit1confirm0': {
        'type': 'confirm',
        'groups': ['pit_1_0', 'pit_1_1'],
        'action': 'buy',
        'occurrence': 1,
        'time_frame_max': 1800,
        'value_range_max': None,
        'rebuy': False,
        'overlap': 5.0,
        'push_max': 2,
        'soft_max': 1,
        'deferred_push': False,
        'push_target': 0.08,
        'stop_percent': 0.15,
        'stop_cutoff': 0.035,
        'follow_all': [
            {
                'groups': ['pit_1_0'],
                'types': ['init4'],
                'min_secs': 0,
                'max_secs': None
            },
            {
                'groups': ['pit_1_1'],
                'types': ['init5'],
                'min_secs': 0,
                'max_secs': None,
            },
        ],
        'conditions': [
            [
                ('ma_position', 6, 0),
            ],
        ]
    },
}
