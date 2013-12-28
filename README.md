README
======

Copyright (C) 2013 Takahiro Yoshimura <altakey@gmail.com>

This is a crude import solver for Java (esp. Android) that doesn't suck too much and isn't huge.


0. HOW TO USE
=============

Say you have config file in ~/.janerc:

    $ cat .janerc
    [native]
    cache-file=~/.jane.cache
    classpath=/usr/local/android-sdk/platforms/android-19/android.jar
    
    [v4]
    cache-file=~/.jane.cache
    classpath=/usr/local/android-sdk/platforms/android-19/android.jar:/usr/local/android-sdk/extras/android/support/v4/android-support-v4.jar

With project:

    $ ls 
    AndroidManifest.xml
    ...
    local.properties
    ...
    $ cat local.properties
    ...
    jane.profile = native

Then, you could do:

    $ solve.py --profile=~/.janerc src/path/to/target.java
    import .....
    import .....
    ....

You can pick some other profile:

    $ solve.py --profile=~/.janerc:v4 src/path/to/target.java
    import .....
    import .....
    ....


If you use emacs, you could put the following to your .emacs to get your lengthy import block generated with quick "C-:":

    $ cat ~/.emacs
    ...
    (defun solve-imports ()
      (interactive)
      (shell-command-on-region
        (region-beginning) (region-end)
        (format "/path/to/solve.py --profile=~/.janerc %s"
          (buffer-file-name))
          t t))
    
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
