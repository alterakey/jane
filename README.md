README
======

Copyright (C) 2013 Takahiro Yoshimura <altakey@gmail.com>

This is a crude import solver for Java (esp. Android) that doesn't suck too much and isn't huge.


0. HOW TO USE
=============

Sample config file:

    $ cat etc/solver.ini
    [native]
    cache-file=~/.solver.cache
    classpath=/usr/local/android-sdk/platforms/android-19/android.jar
    
    [v4]
    cache-file=~/.solver.cache
    classpath=/usr/local/android-sdk/platforms/android-19/android.jar:/usr/local/android-sdk/extras/android/support/v4/android-support-v4.jar

Using from shell:

    $ solve.py --profile=etc/solver.ini:native /path/to/target.java
    import .....
    import .....
    ....

From Elisp:

    $ cat ~/.emacs
    ...
    (defun solve-imports ()
      (interactive)
      (shell-command-on-region
        (region-beginning) (region-end)
        (format "python /path/to/solve.py --profile=/path/to/solver.ini:native %s"
          (buffer-file-name))
          t t))
    
    ;; Then, bind this defun to some key, select import block and invoke over it.
    (global-set-key (kbd "C-:") 'solve-imports)


1. FEATURES
===========

 * Recognizes class/interface/"static final" definitions
 * Recognizes static inner class reference (e.g. XXX.YYY -> import XXX)
 * Generates necessary import block
 * Profile based configuration
 * Current project files are automatically recognized
 * Will not blindly import android.R
 * Symbols are cached in human-readable format (gzipped JSON)

2. BUGS
=======

 * Doesn't recognize static inner classes deeper than 1 level.
 * Symbol recognition logic is stupid and reckless.
 * Assumes some degree of AOSP-ish naming scheme is in use
   (e.g. PUBLIC_STATIC_FINAL_VAR, public_static_final_var, ClassName.)
 * Requires target file existence (i.e. no on-the-fly generation.)
 * Insanely hackish.