from .plugin import blueprint, menu, plugin_load, plugin_unload, plugin_info
from .logic import Logic
try:
    from guessit import guessit
except:
    try:
        os.system("{} install guessit".format(app.config['config']['pip']))
        from guessit import guessit
    except:
        pass
