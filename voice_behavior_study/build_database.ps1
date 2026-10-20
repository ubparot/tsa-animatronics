# Builds VoiceBehaviorStudy.accdb from the CSVs in db_tables\ (made by export_tables.py).
# Re-running replaces the database, so it is safe to rebuild after new listening ratings arrive.
#
#   powershell -NoProfile -ExecutionPolicy Bypass -File .\build_database.ps1

$ErrorActionPreference = 'Stop'
$study = $PSScriptRoot
$dbPath = Join-Path $study 'VoiceBehaviorStudy.accdb'
$tables = Join-Path $study 'db_tables'
$conn = "Provider=Microsoft.ACE.OLEDB.16.0;Data Source=$dbPath"

# Field type codes: T = short text, M = long text, I = whole number, D = decimal number, B = yes/no, DT = date/time
$schema = [ordered]@{
  Prompts = [ordered]@{
    _desc = 'Text each clip was asked to say: three fixed sweep lines plus 42 rewrites of three base sentences.'
    PromptID = 'T|Primary key (P01-P45)'
    PromptText = 'M|Exact text sent to the voice model, including any [tags]'
    Arm = 'T|parameter sweep line or prompt manipulation'
    Category = 'T|Show category: greeting, lie, confession, excited'
    BaseSentence = 'T|A, B or C for prompt-manipulation rows; blank for sweep lines'
    ManipulationCode = 'T|M00-M13 rewrite code'
    Manipulation = 'T|What was changed in the text'
    ManipulationType = 'T|control, punctuation, typography, paralinguistic tag, emotion tag, lexical'
    IntendedEffect = 'T|The delivery change the rewrite is meant to cause'
    IntendedEmotion = 'T|Feeling the line should carry'
    SentenceType = 'T|statement, question or exclamation (from final punctuation)'
    WordCount = 'I|Words a listener should hear (tags removed)'
    HasTag = 'B|Text contains a bracketed sound/emotion tag'
    PunctuationMarks = 'I|Count of , . ! ? ;'
  }
  ParameterSettings = [ordered]@{
    _desc = 'Each experimental condition: one knob changed from its engine baseline.'
    SettingID = 'T|Primary key (S01-S44)'
    Engine = 'T|Chatterbox Turbo, Chatterbox (original), or Kokoro + RVC'
    Arm = 'T|baseline, sampling, audio prompt, guidance, conversion'
    VariableTested = 'T|The one parameter changed in this condition'
    LevelLabel = 'T|Short label for the level'
    IsBaseline = 'B|This row is the engine baseline'
    Notes = 'M|Caveats about this condition'
    Temperature = 'D|Sampling temperature (randomness of the next speech token)'
    TopP = 'D|Nucleus sampling: keep the smallest token set whose probability adds to this'
    TopK = 'I|Keep only the K most likely tokens (Turbo only)'
    MinP = 'D|Drop tokens below this fraction of the top probability (original Chatterbox)'
    RepetitionPenalty = 'D|Penalty on reusing recent speech tokens'
    CFGWeight = 'D|Classifier-free guidance weight (original Chatterbox only)'
    Exaggeration = 'D|Emotion exaggeration (original Chatterbox only)'
    ConversionStrength = 'D|RVC index_rate: how much the target voice''s features replace the source''s'
    Protect = 'D|RVC protect: shields consonants and breaths from conversion (0.5 = off)'
    RmsMix = 'D|RVC rms_mix_rate: 0 keeps the source loudness envelope, 1 uses the converted one'
    ReferenceClip = 'T|Audio prompt clip from the character voice corpus'
    ReferenceStyle = 'T|How the reference clip is delivered'
    PitchShiftSemitones = 'I|RVC pitch shift applied (measured from median F0)'
  }
  Generations = [ordered]@{
    _desc = 'One row per generated clip; joins a prompt to a setting, with the words actually heard.'
    ClipID = 'T|Primary key (C001-C192)'
    SettingID = 'T|Foreign key to ParameterSettings'
    PromptID = 'T|Foreign key to Prompts'
    StudyBlock = 'T|parameter sweep, seed only, or prompt manipulation'
    Engine = 'T|Voice engine (copied from the setting for easy filtering)'
    Seed = 'I|Random seed (same seed everywhere except the seed-only block)'
    DurationSec = 'D|Clip length in seconds'
    IntendedWords = 'M|Words that should be spoken'
    HeardTranscript = 'M|What speech recognition heard'
    WordBehavior = 'T|faithful, dropped, added, repeated, substituted words, read cue aloud'
    WordBehaviorNotes = 'M|Which words changed'
    EndingBehavior = 'T|How the clip ends after the last word'
    InListeningSession = 'B|Clip was in the blind listening session'
    AudioPath = 'T|Where the WAV file is stored'
  }
  AcousticBehavior = [ordered]@{
    _desc = 'Delivery measurements over the spoken part of each clip, with plain-language labels (study-wide thirds).'
    ClipID = 'T|Primary key and foreign key to Generations'
    MeanPitchHz = 'D|Average voice pitch'
    PitchRangeSemitones = 'D|Spread of pitch (5th-95th percentile): melody vs monotone'
    PitchVariabilitySemitones = 'D|Standard deviation of pitch'
    IntonationContour = 'T|level, rising, falling, rising at end'
    TonalityLabel = 'T|monotone / moderate melody / very melodic'
    PauseCount = 'I|Silent gaps of 150 ms or more inside the line'
    LongestPauseSec = 'D|Longest internal gap'
    TotalPauseSec = 'D|Total internal silence'
    PauseLabel = 'T|Plain-language pause pattern'
    SpeechRateSylPerSec = 'D|Syllables per second of speaking time'
    PacingLabel = 'T|slow / moderate / rushed'
    F1Hz = 'D|First formant (higher = more open mouth / brighter vowels)'
    F2Hz = 'D|Second formant (tongue frontness)'
    SpectralCentroidHz = 'D|Brightness of the sound (resonance)'
    ResonanceLabel = 'T|dark/warm / neutral / bright/thin'
    LoudnessDb = 'D|Typical loudness (dB relative to full scale)'
    LoudnessRangeDb = 'D|Loud-to-soft contrast'
    DynamicsLabel = 'T|even volume / some contrast / strong volume swings'
    HNRdB = 'D|Harmonics-to-noise ratio; lower = breathier or rougher'
    BreathinessLabel = 'T|breathy/rough / moderate / clear/pure'
    VoicedFraction = 'D|Share of the line with vocal-fold vibration'
    TrailingSec = 'D|Audio after the last word'
    EndingBehavior = 'T|clean stop, trailing silence, trailing breath/noise, keeps vocalizing'
  }
  ListenerRatings = [ordered]@{
    _desc = 'Blind human ratings from the listening session (settings hidden, order shuffled per listener).'
    RatingID = 'T|Primary key'
    ClipID = 'T|Foreign key to Generations'
    Listener = 'T|Rater initials'
    RatedAt = 'DT|When the rating was saved'
    PerceivedTone = 'T|Tone the listener heard'
    EmotionMatch = 'I|1-5: matches the intended feeling'
    Expressiveness = 'I|1-5: monotone to very animated'
    Naturalness = 'I|1-5: robotic to human'
    Breathiness = 'I|1-5: clear to very breathy'
    Articulation = 'I|1-5: mumbled to crisp'
    CharacterFit = 'I|1-5: sounds like the Pinocchio character'
    Pacing = 'T|too slow, natural, too fast, uneven'
    Oddities = 'M|Anything odd the listener noticed'
    Notes = 'M|Free-text listener notes'
  }
  ScriptVariants = [ordered]@{
    _desc = 'Word choice and phrasing of the show language model (pinocchio-fast) under different sampling.'
    VariantID = 'T|Primary key (V01-V40)'
    QuestionID = 'T|Q1 or Q2'
    VisitorQuestion = 'T|Question asked'
    ShowOutcome = 'T|LIE or CONFESSION the show requested'
    VariableTested = 'T|temperature, top_p, top_k, seed only, or baseline'
    LevelLabel = 'T|Short label for the level'
    Temperature = 'D|Sampling temperature'
    TopP = 'D|Nucleus sampling threshold'
    TopK = 'I|Top-k cutoff'
    Seed = 'I|Random seed'
    GeneratedLine = 'M|What the model wrote for Pinocchio to say'
    ValidJSON = 'B|Reply matched the response schema'
    WordCount = 'I|Words in the line'
    DistinctWordRatio = 'D|Unique words / total words (repetition indicator)'
    OverlapWithBaseline = 'D|Share of vocabulary shared with the baseline line (Jaccard)'
    SentenceCount = 'I|Sentences in the line'
    Exclamations = 'I|Count of !'
    Questions = 'I|Count of ?'
    Commas = 'I|Count of commas (phrasing breaks)'
    OpeningWords = 'T|First three words'
    EndsMidSentence = 'B|Cut off by the 108-character schema limit'
    ToneCode = 'T|Researcher-coded tone'
    FitsOutcome = 'T|yes / partial / no: does the line deliver the requested lie or confession'
    PhrasingNote = 'M|Researcher note on phrasing and word choice'
  }
}

$sqlType = @{ T = 'TEXT(255)'; M = 'LONGTEXT'; I = 'LONG'; D = 'DOUBLE'; B = 'BIT'; DT = 'DATETIME' }
$keys = @{ Prompts = 'PromptID'; ParameterSettings = 'SettingID'; Generations = 'ClipID'; AcousticBehavior = 'ClipID';
           ListenerRatings = 'RatingID'; ScriptVariants = 'VariantID' }
$foreign = @(
  @('Generations', 'SettingID', 'ParameterSettings', 'SettingID'),
  @('Generations', 'PromptID', 'Prompts', 'PromptID'),
  @('AcousticBehavior', 'ClipID', 'Generations', 'ClipID'),
  @('ListenerRatings', 'ClipID', 'Generations', 'ClipID')
)

if (Test-Path $dbPath) { Remove-Item $dbPath -Force -Confirm:$false }
$catalog = New-Object -ComObject ADOX.Catalog
$null = $catalog.Create($conn)
$db = $catalog.ActiveConnection

function Convert-Value($raw, $code) {
  if ($null -eq $raw -or $raw -eq '' -or $raw -eq 'nan' -or $raw -eq 'None') { return [DBNull]::Value }
  switch ($code) {
    'I' { return [int][math]::Round([double]::Parse($raw, [Globalization.CultureInfo]::InvariantCulture)) }
    'D' { return [double]::Parse($raw, [Globalization.CultureInfo]::InvariantCulture) }
    'B' { return [bool]($raw -eq 'True') }
    'DT' { return [datetime]::Parse($raw, [Globalization.CultureInfo]::InvariantCulture) }
    default { return [string]$raw }
  }
}

foreach ($table in $schema.Keys) {
  $csvPath = Join-Path $tables "$table.csv"
  if (-not (Test-Path $csvPath)) { Write-Host "skip $table (no CSV yet)"; continue }
  $fields = $schema[$table]
  $columns = @($fields.Keys | Where-Object { $_ -ne '_desc' })
  $ddl = ($columns | ForEach-Object { "[$_] " + $sqlType[$fields[$_].Split('|')[0]] }) -join ', '
  $null = $db.Execute("CREATE TABLE [$table] ($ddl, CONSTRAINT [PK_$table] PRIMARY KEY ([$($keys[$table])]))")

  $rows = Import-Csv $csvPath -Encoding UTF8
  $placeholders = ($columns | ForEach-Object { '?' }) -join ', '
  $columnList = ($columns | ForEach-Object { "[$_]" }) -join ', '
  foreach ($row in $rows) {
    $cmd = New-Object -ComObject ADODB.Command
    $cmd.ActiveConnection = $db
    $cmd.CommandText = "INSERT INTO [$table] ($columnList) VALUES ($placeholders)"
    foreach ($col in $columns) {
      $code = $fields[$col].Split('|')[0]
      $value = Convert-Value $row.$col $code
      $adoType = @{ T = 202; M = 203; I = 3; D = 5; B = 11; DT = 7 }[$code]
      $size = if ($code -eq 'T') { 255 } elseif ($code -eq 'M') { 65535 } else { 0 }
      $null = $cmd.Parameters.Append($cmd.CreateParameter($col, $adoType, 1, $size, $value))
    }
    $null = $cmd.Execute()
  }
  Write-Host ("{0,-18} {1,3} records  {2,2} fields" -f $table, $rows.Count, $columns.Count)
}

foreach ($fk in $foreign) {
  $exists = $catalog.Tables | Where-Object { $_.Name -eq $fk[0] }
  if (-not $exists) { continue }
  $null = $db.Execute("ALTER TABLE [$($fk[0])] ADD CONSTRAINT [FK_$($fk[0])_$($fk[1])] FOREIGN KEY ([$($fk[1])]) REFERENCES [$($fk[2])] ([$($fk[3])])")
}

# Field and table descriptions show in Access Design View (needs DAO, which ships with Access).
$db.Close()
$null = [Runtime.InteropServices.Marshal]::ReleaseComObject($catalog)
[GC]::Collect(); [GC]::WaitForPendingFinalizers()
$engine = New-Object -ComObject DAO.DBEngine.120
$dao = $engine.OpenDatabase($dbPath)
foreach ($table in $schema.Keys) {
  $tdf = $dao.TableDefs | Where-Object { $_.Name -eq $table }
  if (-not $tdf) { continue }
  $tdf.Properties.Append($tdf.CreateProperty('Description', 10, $schema[$table]['_desc']))
  foreach ($col in @($schema[$table].Keys | Where-Object { $_ -ne '_desc' })) {
    $field = $tdf.Fields.Item($col)
    $field.Properties.Append($field.CreateProperty('Description', 10, $schema[$table][$col].Split('|', 2)[1]))
  }
}
# Saved queries: the example questions the research paper answers by joining tables.
$queries = [ordered]@{
  qrySilencesAndListenerFlags = @"
SELECT s.Engine, s.LevelLabel, g.ClipID, g.PromptID, a.LongestPauseSec, r.Oddities
FROM ((AcousticBehavior AS a INNER JOIN Generations AS g ON a.ClipID = g.ClipID)
  INNER JOIN ParameterSettings AS s ON g.SettingID = s.SettingID)
  LEFT JOIN ListenerRatings AS r ON g.ClipID = r.ClipID
WHERE a.LongestPauseSec > 1
ORDER BY a.LongestPauseSec DESC;
"@
  qryPromptWordChanges = @"
SELECT p.ManipulationCode, p.Manipulation, p.PromptText, g.HeardTranscript, g.WordBehavior
FROM Prompts AS p INNER JOIN Generations AS g ON p.PromptID = g.PromptID
WHERE g.StudyBlock = 'prompt manipulation' AND g.WordBehavior <> 'faithful'
ORDER BY p.ManipulationCode, p.PromptID;
"@
  qryListenerVsMeasures = @"
SELECT r.ClipID, s.Engine, s.LevelLabel, r.Expressiveness, a.MeanPitchHz, a.PitchRangeSemitones,
  r.Pacing, a.SpeechRateSylPerSec, r.Breathiness, a.HNRdB
FROM ((ListenerRatings AS r INNER JOIN AcousticBehavior AS a ON r.ClipID = a.ClipID)
  INNER JOIN Generations AS g ON r.ClipID = g.ClipID)
  INNER JOIN ParameterSettings AS s ON g.SettingID = s.SettingID
ORDER BY r.Expressiveness DESC, a.MeanPitchHz DESC;
"@
  qryRatingsByEngine = @"
SELECT s.Engine, Count(r.RatingID) AS Clips, Avg(r.Naturalness) AS AvgNaturalness,
  Avg(r.Articulation) AS AvgArticulation, Avg(r.CharacterFit) AS AvgCharacterFit, Avg(r.EmotionMatch) AS AvgEmotionMatch
FROM (ListenerRatings AS r INNER JOIN Generations AS g ON r.ClipID = g.ClipID)
  INNER JOIN ParameterSettings AS s ON g.SettingID = s.SettingID
WHERE g.StudyBlock <> 'prompt manipulation'
GROUP BY s.Engine
ORDER BY Avg(r.Naturalness) DESC;
"@
  qryScriptOverlap = @"
SELECT v.VariantID, v.QuestionID, v.VariableTested, v.LevelLabel, v.GeneratedLine, v.OverlapWithBaseline, v.ToneCode, v.FitsOutcome
FROM ScriptVariants AS v
ORDER BY v.QuestionID, v.OverlapWithBaseline DESC;
"@
}
foreach ($name in $queries.Keys) { $null = $dao.CreateQueryDef($name, $queries[$name]) }

$dao.Close()
Write-Host "Built $dbPath (with $($queries.Count) saved queries)"
