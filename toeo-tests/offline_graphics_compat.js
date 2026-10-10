'use strict';
// legacy_graphics_assets.py prepares lossless palette expansion in a separate
// runtime directory. The rejected ValidateDevice hypothesis was removed.
// No memory writes, graphics setters, replacement drawing or HRESULTs here.
send({event:'offline_graphics_compat_ready',
  note:'Palette assets prepared on disk; original native drawing and game state untouched'});
