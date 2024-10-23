import logging
import logging.config

logging.config.dictConfig({
    'version': 1,
    'formatters': {
        'default': {
            'format': '[%(asctime)s] [%(name)s] [%(levelname)s] [%(funcName)s] [%(lineno)d] > %(message)s',
            'datefmt': '%Y-%m-%d %H:%M:%S'
        }
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'level': 'DEBUG',
            'formatter': 'default',
            'stream': 'ext://sys.stdout'
        }
    },
    'loggers': {
        'requests': {
            'level': 'DEBUG'
        },
        'urllib3': {
            'level': 'DEBUG'
        },
        'polling': {
            'level': 'DEBUG'
        },
        'homework': {
            'level': 'DEBUG'
        },
    },
    'root': {
        'level': 'INFO',
        'handlers': ['console']
    }
})
