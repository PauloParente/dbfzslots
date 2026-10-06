=====================================================================
  DBFZ SLOTS - INSTALLER (BETA)
=====================================================================

Adds modded characters to DRAGON BALL FighterZ as NEW SLOTS (a 4th
row on the character select screen, up to 15 characters) without
replacing any original character. Each one gets its own icon,
portraits, name and command list.

  >> OFFLINE PLAY ONLY, ON A COPY OF THE GAME. <<

  - This package does NOT include or create a game executable and
    does NOT disable the anti-cheat. It works with an offline exe
    you already have (RED\Binaries\Win64\...eac-nop...exe).
  - Never use the modded copy online.
  - Modifying the game may break its terms of use. You do this at
    your own risk.


HOW TO USE
----------
1. Make a COPY of your game folder (for example copy
   ...\steamapps\common\DRAGON BALL FighterZ to D:\DBFZ Mods).
   Your Steam install must stay untouched.

2. Open Unverum, point it to the COPY and apply your mods there.
   Unverum also creates the offline exe in the copy:
     RED\Binaries\Win64\RED-Win64-Shipping-eac-nop-loaded.exe
   Character moveset mods installed by Unverum are fine: the
   installer turns them into new slots automatically.

3. Put the character mods you want as new slots in one folder
   (.zip, .rar, or Unverum mod folders). Do not extract the archives.
   (Character mods you already applied with Unverum are picked up
   from the copy, they do not need to be in this folder.)

4. Open DBFZSlots-Installer and choose:
     - Game folder: your COPY (the folder that contains RED)
     - Mods folder: the folder from step 3

5. Click APPLY and wait (a few minutes).

6. Start the game with the offline exe in the copy (or from Unverum).

IMPORTANT: after you change mods in Unverum (it reinstalls its
files), click Apply again in this installer.

To add, remove or reorder characters later: change the mods folder
and click Apply again.

Known mods (tested recipes) are recognized automatically by their
file. Other mods are detected automatically: most character mods
work, but untested ones may have missing effects or sounds.


ADVANCED (optional)
-------------------
Tick "Advanced" in the installer to:
  - choose the offline exe or a different AES key;
  - "Analyze only": list the characters first, then reorder them on
    the 4th row (Move up / Move down), rename them (Edit) or remove
    some before clicking Apply.


WHAT THE INSTALLER CHANGES IN THE GAME COPY
-------------------------------------------
- RED\Binaries\Win64:
    dsound.dll (Ultimate ASI Loader)
    plugins\DBFZSlots.asi and plugins\DBFZSlots\ (settings, profile, log)
    opengl32.dll and ue4ss\ (UE4SS and the icon script)
- RED\Content\Paks\~mods\DBFZSlots\: the converted characters.
- Its own save files in the UserData folder (kept apart from your
  Steam saves).
- Unverum character moveset paks are converted into new slots and
  then disabled (moved to DBFZSlots_data\backup\). Your other Unverum
  mods (skins, costumes, stages...) are not touched. Files the
  installer replaces are backed up to DBFZSlots_data\backup\.


SETTINGS (RED\Binaries\Win64\plugins\DBFZSlots\slots.ini)
------------------------------------------------------------
  grid_shift=64      moves the character grid up (64 = one row) so the
                     4th row does not sit under the button guide.
                     Click Apply again after changing it.
  separate_saves=1   saves of this copy go to UserData\ (0 = same
                     saves as the Steam game).


IF SOMETHING GOES WRONG
-----------------------
- "this is the Steam folder": choose your copy, not the Steam install.
- "could not find a single offline exe": apply Unverum to the copy
  first (it creates the offline exe). The installer does not create it.
- "this exe is not compatible": your game version changed something
  the plugin needs. Nothing was installed. Send the error text.
- A problem inside the game: send these two files from the copy:
    RED\Binaries\Win64\plugins\DBFZSlots\dbfzslots.log
    RED\Binaries\Win64\plugins\DBFZSlots\profile.txt
- Command line mode:
    DBFZSlots-Installer.exe --cli --game ... --mods ...
  (add --dry-run to see everything without installing)


CREDITS
-------
- Characters: every mod belongs to its author (see each mod's page on
  GameBanana).
- Extra slots concept: WistfulHopes (DBFZ Custom Character Slots) and
  MrPopulutus (DBFZ-ExtrasCustomSlots, MIT license).
- Third-party components: see THIRD-PARTY.txt.
