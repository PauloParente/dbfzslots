=====================================================================
  DBFZ SLOTS - INSTALLER (BETA)
=====================================================================

Adds modded characters to DRAGON BALL FighterZ as NEW SLOTS (a 4th
row on the character select screen, up to 15 characters) without
replacing any original character. Each one gets its own icon,
portraits, name and command list.

  >> OFFLINE PLAY ONLY. <<

  - The mod is only active while you play from this installer's
    PLAY button (or the "DBFZ Slots" desktop shortcut). Opening the
    game from Steam starts the normal game, without mods.
  - This package does NOT include or create a game executable and
    does NOT disable the anti-cheat. It works with the offline exe
    Unverum creates (RED\Binaries\Win64\...eac-nop...exe).
  - Modifying the game may break its terms of use. You do this at
    your own risk.


HOW TO USE
----------
1. In Unverum, install the character moveset mods you want and apply
   them to your game once (the Steam folder is fine). This also
   creates the offline exe the installer needs.

2. Open DBFZSlots-Installer. It finds by itself:
     - your DRAGON BALL FighterZ folder (from Steam), and
     - Unverum's Dragon Ball FighterZ mods folder,
   and lists every character mod in them. Skins, stages and other
   mods that are not characters are left out. If something is not
   found, click "Change..." on that line. Any folder with .zip / .rar
   mods (do not extract them) or mod folders also works.

3. In the list:
     - tick the characters you want (up to 15),
     - drag them to set their order on the 4th row,
     - double-click one to rename it.

4. Click PLAY. The first time it builds the characters (a few
   minutes). After that it only rebuilds when something changed (new
   mods, other choices, Unverum changes), otherwise the game starts
   right away. While you play, the installer waits in the tray (next
   to the clock); when the game closes, it takes the mod out again.

The installer also creates a "DBFZ Slots" shortcut on your desktop
that does the same as PLAY.

Characters converted from Unverum are kept in
DBFZSlots_data\imported\chars (delete a folder there to remove one).

IF THE GAME CRASHES
The installer waits for the game to close, so it cleans up by itself
even if the game crashes. Files are only left behind if the PC itself
crashes (or the installer is closed while you play). Then the
installer shows a warning with a "Restore normal game" button (PLAY
also cleans up first). Even with leftovers, the plugin never runs
inside the Steam exe.

Known mods (tested recipes) are recognized automatically by their
file. Other mods are detected automatically: most character mods
work, but untested ones may have missing effects or sounds.


WHAT THE INSTALLER CHANGES IN THE GAME FOLDER
---------------------------------------------
- DBFZSlots_data\ (in the game folder): everything the mod needs,
  kept in DBFZSlots_data\ready while you are not playing, plus
  backups of anything it replaced or disabled.
- Only while the game runs from PLAY:
    RED\Binaries\Win64\dsound.dll (Ultimate ASI Loader), opengl32.dll
    and ue4ss\ (UE4SS), plugins\DBFZSlots.asi and plugins\DBFZSlots\,
    RED\Content\Paks\~mods\DBFZSlots\ (the converted characters).
  If another tool has its own dsound.dll there (Unverum does), it is
  set aside while you play and put back afterwards.
- Its own save files in the UserData folder (kept apart from your
  Steam saves).
- Unverum character moveset paks are converted into new slots and
  then disabled (moved to DBFZSlots_data\backup\). Your other Unverum
  mods (skins, costumes, stages...) are not touched.


SETTINGS (DBFZSlots_data\ready\RED\Binaries\Win64\plugins\DBFZSlots\slots.ini)
--------------------------------------------------------------------------
  grid_shift=64      moves the character grid up (64 = one row) so the
                     4th row does not sit under the button guide.
                     PLAY applies the change by itself.
  separate_saves=1   modded saves go to UserData\ (0 = same saves
                     as the normal game).


IF SOMETHING GOES WRONG
-----------------------
- Every error message says what to do. "Copy log" (in the installer)
  copies everything needed to report a problem: paste it in your
  message.
- "Offline exe: not found": apply Unverum to the game folder first
  (it creates the offline exe). The installer does not create it.
- "this exe is not compatible": your game version changed something
  the plugin needs. Nothing was installed. Click "Copy log" and send it.
- Command line mode:
    DBFZSlots-Installer.exe --cli --game ... --mods ...
  (add --dry-run to see everything without installing)
    DBFZSlots-Installer.exe --play   (what the shortcut does)
    DBFZSlots-Installer.exe --restore "<game folder>"  (take the mod out now)


CREDITS
-------
- Characters: every mod belongs to its author (see each mod's page on
  GameBanana).
- Extra slots concept: WistfulHopes (DBFZ Custom Character Slots) and
  MrPopulutus (DBFZ-ExtrasCustomSlots, MIT license).
- Third-party components: see THIRD-PARTY.txt.
