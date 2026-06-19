class Main {
    Description = "Stay above your configured speed threshold and avoid crashes.";

    RunLength = 120.0;
    RunLengthTooltip = "Length of the run in seconds";

    FlyThreshold = 100.0;
    FlyThresholdTooltip = "Speed required to start a flight segment";

    CrashMargin = 10.0;
    CrashMarginTooltip = "Speed buffer so tiny dips don't instantly count as crashing";

    CrashGraceTime = 0.25;
    CrashGraceTimeTooltip = "Seconds below the crash speed before a crash registers";

    MinFlightTime = 1.0;
    MinFlightTimeTooltip = "Flight segments shorter than this do not count as crashes";

    InfiniteGas = true;
    InfiniteGasTooltip = "Keeps gas full during the run";

    Heatmap = true;
    HeatmapTooltip = "Write map data to PersistentData/bombs_heatmap.txt for optional density and crash map images";

    UiPrimaryColor = "white";
    UiPrimaryColorTooltip = "Color name (e.g. red) or HEX color code (e.g. #ff0000). Invalid colors show as white";

    UiAccentColor = "yellow";
    UiAccentColorTooltip = "Color name (e.g. red) or HEX color code (e.g. #ff0000). Invalid colors show as white";

    function OnGameStart() {
        if (Network.IsMasterClient) {
            Utils.PauseGame();
        }

        Utils.ClampSettings();
    }

    function OnPlayerSpawn(player, character) {
        if (character.IsMainCharacter && character.IsMine) {
            Run._playerCharacter = character;
            Run.ResetStats();

            player.ClearKDR();

            Utils.ResumeGame();
        }
    }

    function OnTick() {
        if (Game.IsEnding || Run._isFinished || Run._playerCharacter == null || !Run._playerCharacter.IsMine) {
            return;
        }

        Run.UpdateTimer();
        Run.TrackFlight();
        Heatmap.TrySample();
        Run.UpdateTopCenter();

        if (Main.InfiniteGas) {
            Run._playerCharacter.CurrentGas = Run._playerCharacter.MaxGas;
        }
    }

    function OnSecond() {
        if (Run._playerCharacter == null || !Run._playerCharacter.IsMine) {
            return;
        }

        Run.OnSecondTick();
        Run.UpdateUI();
    }

    function OnCharacterDie(victim, killer, killerName) {
        if (Run._playerCharacter != null && victim == Run._playerCharacter && victim.IsMine && !Run._isFinished) {
            Run.EndRun();
        }
    }

    function OnButtonClick(button) {
        if (button == "Restart") {
            Game.End(0);
        }
    }
}

extension Run {
    _isFinished = false;
    _playerCharacter = null;

    _runStartTime = 0.0;

    _isFlying = false;
    _segmentStartTime = 0.0;
    _belowThresholdSince = -1.0;

    _crashes = 0;
    _highestSpeed = 0.0;
    _speedSecondSum = 0.0;
    _speedSecondSamples = 0;

    _timeAboveThreshold = 0.0;
    _streakStartTime = 0.0;
    _maxStreak = 0.0;

    function ResetStats() {
        self._isFinished = false;
        self._isFlying = false;

        self._runStartTime = Time.GameTime;

        self._segmentStartTime = 0.0;
        self._belowThresholdSince = -1.0;

        self._crashes = 0;
        self._highestSpeed = 0.0;
        self._speedSecondSum = 0.0;
        self._speedSecondSamples = 0;

        self._timeAboveThreshold = 0.0;
        self._streakStartTime = Time.GameTime;
        self._maxStreak = 0.0;

        Heatmap.Reset();
    }

    function GetElapsedTime() {
        return Time.GameTime - self._runStartTime;
    }

    function GetTimeRemaining() {
        remaining = Main.RunLength - self.GetElapsedTime();

        if (remaining < 0.0) {
            remaining = 0.0;
        }

        return remaining;
    }

    function IsAboveThreshold() {
        if (self._playerCharacter == null) {
            return false;
        }

        return Utils.GetCharacterSpeed(self._playerCharacter) >= Main.FlyThreshold;
    }

    function GetCrashSpeedThreshold() {
        threshold = Main.FlyThreshold - Main.CrashMargin;

        if (threshold < 0.0) {
            threshold = 0.0;
        }

        return threshold;
    }

    function UpdateTimer() {
        if (self.GetElapsedTime() >= Main.RunLength) {
            self.EndRun();
        }
    }

    function OnSecondTick() {
        if (self._isFinished) {
            return;
        }

        if (self._playerCharacter != null) {
            speed = Utils.GetCharacterSpeed(self._playerCharacter);

            self._speedSecondSum += speed;
            self._speedSecondSamples += 1;

            if (speed >= Main.FlyThreshold) {
                self._timeAboveThreshold += 1.0;
            }
        }

        streak = self.GetCurrentStreak();
        if (streak > self._maxStreak) {
            self._maxStreak = streak;
        }
    }

    function TrackFlight() {
        speed = Utils.GetCharacterSpeed(self._playerCharacter);

        if (speed > self._highestSpeed) {
            self._highestSpeed = speed;
        }

        if (speed >= Main.FlyThreshold) {
            if (!self._isFlying) {
                self._segmentStartTime = Time.GameTime;
            }

            self._isFlying = true;
            self._belowThresholdSince = -1.0;
            return;
        }

        if (!self._isFlying) {
            return;
        }

        crashThreshold = self.GetCrashSpeedThreshold();

        if (speed >= crashThreshold) {
            self._belowThresholdSince = -1.0;
            return;
        }

        if (self._belowThresholdSince < 0.0) {
            self._belowThresholdSince = Time.GameTime;
        }

        if (Time.GameTime - self._belowThresholdSince >= Main.CrashGraceTime) {
            self.TryRegisterCrash();
        }
    }

    function TryRegisterCrash() {
        duration = Time.GameTime - self._segmentStartTime;

        if (duration < Main.MinFlightTime) {
            self.ClearSegment();
            return;
        }

        self.RegisterCrash();
    }

    function RegisterCrash() {
        self._crashes += 1;
        self._streakStartTime = Time.GameTime;
        Heatmap.TryRecordCrash();
        self.ClearSegment();
    }

    function FinishCurrentFlight() {
        if (!self._isFlying) {
            return;
        }

        self.ClearSegment();
    }

    function ClearSegment() {
        self._isFlying = false;
        self._segmentStartTime = 0.0;
        self._belowThresholdSince = -1.0;
    }

    function GetCurrentStreak() {
        return Time.GameTime - self._streakStartTime;
    }

    function GetTimeAboveThresholdPercent() {
        elapsed = self.GetElapsedTime();

        if (elapsed <= 0.0) {
            return 0.0;
        }

        return (self._timeAboveThreshold / elapsed) * 100.0;
    }

    function GetAverageSpeed() {
        if (self._speedSecondSamples <= 0) {
            return 0.0;
        }

        return self._speedSecondSum / self._speedSecondSamples;
    }

    function EndRun() {
        if (self._isFinished) {
            return;
        }

        self._isFinished = true;
        self.FinishCurrentFlight();

        streak = self.GetCurrentStreak();
        if (streak > self._maxStreak) {
            self._maxStreak = streak;
        }

        Heatmap.Save();

        Utils.PauseGame();

        CustomUI.ClearLiveLabels();
        CustomUI.ShowEndScreen();
    }

    function UpdateTopCenter() {
        if (self._isFinished) {
            return;
        }

        speed = 0.0;

        if (self._playerCharacter != null) {
            speed = Utils.GetCharacterSpeed(self._playerCharacter);
        }

        CustomUI.ShowTopCenter(self.GetTimeRemaining(), speed, self.IsAboveThreshold());
    }

    function UpdateUI() {
        if (self._isFinished) {
            return;
        }

        self.UpdateTopCenter();
        CustomUI.ShowTopLeft(self._crashes, self.GetCurrentStreak());
    }
}

extension Heatmap {
    _exportFile = "bombs_heatmap";
    _gridSize = 96;
    _minX = -648.0;
    _maxX = 648.0;
    _minZ = -648.0;
    _maxZ = 648.0;
    _sampleInterval = 0.2;
    _skipSeconds = 5.0;
    _lastSampleTime = 0.0;
    _cells = Dict();
    _pathPoints = List();
    _crashPoints = List();

    function IsInBounds(x, z) {
        return x >= self._minX && x <= self._maxX && z >= self._minZ && z <= self._maxZ;
    }

    function Reset() {
        if (!Main.Heatmap) {
            return;
        }

        self._cells = Dict();
        self._pathPoints = List();
        self._crashPoints = List();
        self._lastSampleTime = 0.0;
    }

    function TrySample() {
        if (!Main.Heatmap) {
            return;
        }

        if (Run._playerCharacter == null) {
            return;
        }

        if (Run.GetElapsedTime() < self._skipSeconds) {
            return;
        }

        if (Time.GameTime - self._lastSampleTime < self._sampleInterval) {
            return;
        }

        self._lastSampleTime = Time.GameTime;

        pos = Run._playerCharacter.Position;
        self.AddPoint(pos.X, pos.Z);

        if (self.IsInBounds(pos.X, pos.Z)) {
            self.RecordPathPoint(pos.X, pos.Z, Run.GetElapsedTime());
        }
    }

    function RecordPathPoint(x, z, elapsed) {
        self._pathPoints.Add(
            String.FormatFloat(x, 1) + "," + String.FormatFloat(z, 1) + "," + String.FormatFloat(elapsed, 2)
        );
    }

    function TryRecordCrash() {
        if (!Main.Heatmap) {
            return;
        }

        if (Run._playerCharacter == null) {
            return;
        }

        pos = Run._playerCharacter.Position;

        if (!self.IsInBounds(pos.X, pos.Z)) {
            return;
        }

        self._crashPoints.Add(
            String.FormatFloat(pos.X, 1) + "," + String.FormatFloat(pos.Z, 1) + "," + String.FormatFloat(Run.GetElapsedTime(), 2)
        );
    }

    function AddPoint(x, z) {
        if (!self.IsInBounds(x, z)) {
            return;
        }

        gridSize = self._gridSize;
        cellW = (self._maxX - self._minX) / Convert.ToFloat(gridSize);
        cellH = (self._maxZ - self._minZ) / Convert.ToFloat(gridSize);

        ix = Math.Floor((x - self._minX) / cellW);
        iz = Math.Floor((z - self._minZ) / cellH);

        if (ix < 0) {
            ix = 0;
        }

        if (iz < 0) {
            iz = 0;
        }

        if (ix >= gridSize) {
            ix = gridSize - 1;
        }

        if (iz >= gridSize) {
            iz = gridSize - 1;
        }

        key = Convert.ToString(ix) + "," + Convert.ToString(iz);
        count = self._cells.Get(key, 0);

        if (count == null) {
            count = 0;
        }

        self._cells.Set(key, count + 1);
    }

    function Save() {
        if (!Main.Heatmap) {
            return;
        }

        if (!PersistentData.IsValidFileName(self._exportFile)) {
            return;
        }

        parts = List();
        keys = self._cells.Keys;

        for (i in Range(0, keys.Count, 1)) {
            key = keys.Get(i);
            count = self._cells.Get(key, 0);

            if (count == null) {
                count = 0;
            }

            parts.Add(key + "," + Convert.ToString(count));
        }

        PersistentData.Clear();
        PersistentData.SetProperty("version", 3);
        PersistentData.SetProperty("gridSize", self._gridSize);
        PersistentData.SetProperty("minX", self._minX);
        PersistentData.SetProperty("maxX", self._maxX);
        PersistentData.SetProperty("minZ", self._minZ);
        PersistentData.SetProperty("maxZ", self._maxZ);
        PersistentData.SetProperty("maxStreak", Run._maxStreak);
        PersistentData.SetProperty("cells", String.Join(parts, ";"));
        PersistentData.SetProperty("path", String.Join(self._pathPoints, ";"));
        PersistentData.SetProperty("crashes", String.Join(self._crashPoints, ";"));
        PersistentData.SaveToFile(self._exportFile, false);

        Game.Print("Map data saved to PersistentData/bombs_heatmap.txt");
    }
}

extension CustomUI {
    function ClearLiveLabels() {
        UI.SetLabelAll("TopCenter", "");
        UI.SetLabelAll("TopLeft", "");
    }

    function ShowTopCenter(remaining, speed, aboveThreshold) {
        speedColor = Main.UiAccentColor;

        if (!aboveThreshold) {
            speedColor = Main.UiPrimaryColor;
        }

        labelText =
            "<color=" + Main.UiPrimaryColor + ">" +
            "<size=32><color=" + Main.UiAccentColor + ">" + String.FormatFloat(remaining, 0) + "s</color></size>" +
            String.Newline +
            "<size=22><color=" + speedColor + ">" + String.FormatFloat(speed, 0) + "</color>" +
            " / " + String.FormatFloat(Main.FlyThreshold, 0) +
            "</size></color>";

        UI.SetLabelAll("TopCenter", labelText);
    }

    function ShowTopLeft(crashes, sinceCrash) {
        hudText =
            "<color=" + Main.UiPrimaryColor + ">" +
            "<size=20>" + Convert.ToString(crashes) + " crashes" +
            " · <color=" + Main.UiAccentColor + ">" + String.FormatFloat(sinceCrash, 0) + "s</color>" +
            " since crash</size></color>";

        UI.SetLabelAll("TopLeft", hudText);
    }

    function BuildRunConfigLine() {
        return "Run " + String.FormatFloat(Main.RunLength, 0) + "s, threshold " + String.FormatFloat(Main.FlyThreshold, 0);
    }

    function BuildRunSummary() {
        timeAbovePercent = Run.GetTimeAboveThresholdPercent();

        return Convert.ToString(Run._crashes) + " crashes" + String.Newline +
            self.BuildRunConfigLine() + String.Newline +
            "Average speed: " + String.FormatFloat(Run.GetAverageSpeed(), 0) + String.Newline +
            "Peak speed: " + String.FormatFloat(Run._highestSpeed, 0) + String.Newline +
            "Above threshold: " + String.FormatFloat(timeAbovePercent, 0) + "%" + String.Newline +
            "Longest without crash: " + String.FormatFloat(Run._maxStreak, 0) + "s";
    }

    function ShowEndScreen() {
        timeAbovePercent = Run.GetTimeAboveThresholdPercent();
        popupWidth = Utils.GetEndPopupWidth();
        popupHeight = Utils.GetEndPopupHeight();

        UI.CreatePopup("Finished", "Run Finished", popupWidth, popupHeight);
        UI.AddPopupLabel("Finished", "<b>" + Convert.ToString(Run._crashes) + " crashes</b>");
        UI.AddPopupLabel("Finished", self.BuildRunConfigLine());
        UI.AddPopupLabel("Finished", "Average Speed: " + String.FormatFloat(Run.GetAverageSpeed(), 0));
        UI.AddPopupLabel("Finished", "Peak Speed: " + String.FormatFloat(Run._highestSpeed, 0));
        UI.AddPopupLabel("Finished", "Above Threshold: " + String.FormatFloat(timeAbovePercent, 0) + "%");
        UI.AddPopupLabel("Finished", "Longest Without Crash: " + String.FormatFloat(Run._maxStreak, 0) + "s");

        Game.Print(self.BuildRunSummary());

        UI.AddPopupBottomButton("Finished", "Restart", "Restart");
        UI.ShowPopup("Finished");
    }
}

extension Utils {
    function PauseGame() {
        Time.TimeScale = 0.0;
    }

    function ResumeGame() {
        Time.TimeScale = 1.0;
    }

    function ClampSettings() {
        if (Main.RunLength <= 0.0) {
            Main.RunLength = 1.0;
        }

        if (Main.FlyThreshold < 0.0) {
            Main.FlyThreshold = 0.0;
        }

        if (Main.CrashMargin < 0.0) {
            Main.CrashMargin = 0.0;
        }

        if (Main.CrashGraceTime < 0.0) {
            Main.CrashGraceTime = 0.0;
        }

        if (Main.MinFlightTime < 0.0) {
            Main.MinFlightTime = 0.0;
        }
    }

    function GetCharacterSpeed(character) {
        return character.Velocity.Magnitude;
    }

    function GetEndPopupWidth() {
        dims = Input.GetScreenDimensions();
        minDimension = Math.Min(dims.X, dims.Y);

        return Convert.ToInt(minDimension * 0.55);
    }

    function GetEndPopupHeight() {
        dims = Input.GetScreenDimensions();
        minDimension = Math.Min(dims.X, dims.Y);

        return Convert.ToInt(minDimension * 0.78);
    }
}
