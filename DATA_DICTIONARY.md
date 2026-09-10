# Data Dictionary

Every column stored by this pipeline: what it is, what unit it is in, and what will burn you if you use it naively.

**This file is generated.** `schema.yaml` is the single source of truth, and `audit.py` reads the same file for its applicability conditions and plausible ranges. That is deliberate: when the documentation and the checks are two hand-maintained copies of the same facts, they drift, and the documentation is the copy that drifts silently.

**Availability is measured, not asserted.** Savant adds and drops columns between seasons. Where a column carries a 'since' season below, treat it as a prior to be checked against the coverage table in the audit report, not as ground truth.

**Sign conventions are the most common silent error in this data.** Anything marked with a warning below has a sign or frame of reference that is easy to get backwards, and getting it backwards produces plausible-looking numbers rather than an error.

**Definitions reconciled against Savant's own CSV documentation on 2026-09-10.** Where this file and that page disagreed, the page won; where the page is silent, the entry says so and the value was inferred from the data.

---

## `pitches`

One row per pitch, roughly 700,000 per full season. Source: `pybaseball.statcast()`, which wraps Baseball Savant's CSV search endpoint.

There is NO primary key -- Savant does not ship one, and re-ingesting a day would duplicate it, which is why `ingest_log` exists. `(game_pk, at_bat_number, pitch_number)` is unique in practice and is the key to use for joins and dedup checks.

### Identity and context

| Column | Unit | Meaning |
|---|---|---|
| `game_pk` | int | MLB's game identifier. Join key to any other MLB data source. |
| `game_date` | YYYY-MM-DD | Date of the game. Stored as text so string comparison sorts correctly. |
| `game_year` | int | Season. Use this rather than parsing game_date. |
| `game_type` | code | R regular, S spring, F/D/L/W postseason rounds, E exhibition. ⚠️ **Filter to 'R' for every leaderboard-style metric. Spring training and postseason rows contaminate qualified-player statistics.** |
| `home_team` | code | Home team, three-letter code. Not stable across relocations. |
| `away_team` | code | Away team, three-letter code. |
| `inning` | int | Inning number. |
| `inning_topbot` | code | Top or Bot. |
| `at_bat_number` | int | Sequential within the game, across both teams. |
| `pitch_number` | int | Sequential within the plate appearance. |
| `batter` | id | MLBAM player ID of the batter. The join key for batter-level work. |
| `pitcher` | id | MLBAM player ID of the pitcher. |
| `stand` | code | Batter handedness, L or R. |
| `p_throws` | code | Pitcher handedness, L or R. |
| `player_name` | text | Player name as Savant supplies it. ⚠️ **This is the PITCHER's name, not the batter's, regardless of the player_type used in the query. A long-standing Savant quirk that has silently corrupted a great deal of public analysis. Join on batter/pitcher IDs instead.** |
| `des` | text | Free-text play description. |
| `fielder_2` | id | MLBAM ID of the fielder at position 2. fielder_2 is the catcher. |
| `fielder_3` | id | MLBAM ID of the fielder at position 3. |
| `fielder_4` | id | MLBAM ID of the fielder at position 4. |
| `fielder_5` | id | MLBAM ID of the fielder at position 5. |
| `fielder_6` | id | MLBAM ID of the fielder at position 6. |
| `fielder_7` | id | MLBAM ID of the fielder at position 7. |
| `fielder_8` | id | MLBAM ID of the fielder at position 8. |
| `fielder_9` | id | MLBAM ID of the fielder at position 9. |

### Count, base-out and score state

| Column | Unit | Meaning |
|---|---|---|
| `balls` | int | Ball count BEFORE this pitch. Plausible range 0 to 3. |
| `strikes` | int | Strike count BEFORE this pitch. Plausible range 0 to 2. |
| `outs_when_up` | int | Outs before the plate appearance. Plausible range 0 to 2. |
| `on_1b` | id | MLBAM ID of the runner on first, NULL if the base is empty. Populated on all pitches (null = base empty, not missing). ⚠️ **Not a 0/1 flag. The test is `on_1b IS NOT NULL`.** |
| `on_2b` | id | MLBAM ID of the runner on second, NULL if empty. Populated on all pitches (null = base empty, not missing). |
| `on_3b` | id | MLBAM ID of the runner on third, NULL if empty. Populated on all pitches (null = base empty, not missing). |
| `home_score` | runs | Home score before the pitch. |
| `away_score` | runs | Away score before the pitch. |
| `post_home_score` | runs | Home score after the pitch. |
| `post_away_score` | runs | Away score after the pitch. |
| `bat_score` | runs | Batting team's score before the pitch. |
| `fld_score` | runs | Fielding team's score before the pitch. |
| `post_bat_score` | runs | Batting team's score after the pitch. |
| `post_fld_score` | runs | Fielding team's score after the pitch. |
| `home_score_diff` | runs | Home score minus away score. |
| `bat_score_diff` | runs | Batting team's score differential. |
| `home_win_exp` | prob 0-1 | Home team win expectancy before the pitch. |
| `bat_win_exp` | prob 0-1 | Batting team win expectancy before the pitch. |
| `delta_home_win_exp` | prob | Change in the home team's win expectancy across the PLATE APPEARANCE. ⚠️ **Two things to keep straight. It is signed to the HOME team, not to whoever did something good. And it is measured per plate appearance, while delta_run_exp is per PITCH -- different denominators, so they cannot be summed together.** |
| `if_fielding_alignment` | code | Standard, Infield shift, or Strategic. ⚠️ **The 2023 shift restrictions make this non-comparable across the 2022/2023 boundary. 'Infield shift' means something different before and after.** |
| `of_fielding_alignment` | code | Standard, Strategic, or 4th outfielder. |

### Pitch characteristics

| Column | Unit | Meaning |
|---|---|---|
| `pitch_type` | code | Two-letter code: FF four-seam, SI sinker, SL slider, ST sweeper, SV slurve, CU curve, KC knuckle-curve, CH change, FS splitter, FC cutter, KN knuckleball, EP eephus, PO pitchout. ⚠️ **ST and SV were introduced in 2023. Sweepers before that are classified as SL, so a pitch-type time series crossing 2022 into 2023 has a discontinuity that is a relabelling, not a trend.** |
| `pitch_name` | text | Human-readable form of pitch_type. |
| `release_speed` | mph | Velocity out of hand, measured ~50 ft from the plate. Plausible range 50 to 106. |
| `effective_speed` | mph | Perceived velocity, adjusted for extension. A short-extension 95 plays slower than a long-extension 95. Plausible range 50 to 110. |
| `release_spin_rate` | rpm | Spin rate at release. Plausible range 500 to 3600. |
| `spin_axis` | degrees 0-360 | Inferred spin axis, clock-face converted. |
| `release_pos_x` | feet | Horizontal release point, catcher's view. |
| `release_pos_z` | feet | Vertical release point. |
| `release_pos_y` | feet | Distance from home plate at release; approximately 60.5 minus extension. |
| `release_extension` | feet | How far in front of the rubber the ball is released. Plausible range 3.0 to 8.5. |
| `pfx_x` | feet | Horizontal movement versus a spinless pitch. Plausible range -3 to 3. ⚠️ **Signed by direction, not by handedness. Multiply by -1 for left-handed pitchers before pooling, or arm-side and glove-side movement cancel.** |
| `pfx_z` | feet | Vertical movement versus a spinless pitch. Plausible range -3 to 3. |
| `plate_x` | feet | Horizontal location at the front of the plate; 0 is the centre of the plate. Plausible range -4 to 4. ⚠️ **For platoon-neutral work, flip by batter handedness. audit.py reports mean plate_x by `stand` so the sign convention is confirmed empirically rather than assumed.** |
| `plate_z` | feet | Height at the front of the plate; 0 is the ground. Plausible range -2 to 7. |
| `sz_top` | feet | Top of the strike zone for this batter on this pitch. Plausible range 2.5 to 4.8. ⚠️ **THE STRIKE ZONE DEFINITION CHANGES IN 2026. Through 2025 sz_top and sz_bot were set by a human operator per pitch and varied continuously; from 2026 they are ABS-defined, derived from batter height. This database shows it starkly: 348,556 distinct sz_top values in 2025 against 390 in 2026. Every zone-derived metric -- zone rate, chase rate, called-strike rate, edge command, catcher framing -- has a hard discontinuity at 2026 that is a MEASUREMENT change, not a behaviour change. Framing value in particular should collapse toward zero in 2026 by construction.** |
| `sz_bot` | feet | Bottom of the strike zone for this batter on this pitch. Plausible range 0.8 to 2.5. ⚠️ **See sz_top: ABS-defined from 2026, operator-set before that.** |
| `zone` | int | 1-9 inside the zone (3x3 grid, catcher's view), 11-14 the outside quadrants. |
| `vx0` | ft/s | Velocity component at y = 50 ft, horizontal. |
| `vy0` | ft/s | Velocity component at y = 50 ft, toward the plate. Large and negative. |
| `vz0` | ft/s | Velocity component at y = 50 ft, vertical. |
| `ax` | ft/s^2 | Acceleration, horizontal. |
| `ay` | ft/s^2 | Acceleration, toward the plate. |
| `az` | ft/s^2 | Acceleration, vertical. Includes gravity, so roughly -32 plus Magnus. |
| `api_break_z_with_gravity` | inches | Total vertical break including gravity: the drop a hitter actually sees. |
| `api_break_x_arm` | inches | Horizontal break toward the arm side. Already handedness-corrected, unlike pfx_x. |
| `api_break_x_batter_in` | inches | Horizontal break toward the batter. |
| `arm_angle` | degrees | Angle between a line parallel to the ground and a line from the pitcher's shoulder to the ball at release. 0 is sidearm, 90 is straight over the top. Plausible range -20 to 100. |

### Outcome

| Column | Unit | Meaning |
|---|---|---|
| `type` | code | B ball, S strike, X in play. ⚠️ **`type = 'X'` is the only reliable test for contact. See estimated_woba_using_speedangle.** |
| `description` | text | Detailed pitch result: called_strike, swinging_strike, foul, hit_into_play, ball, blocked_ball, hit_by_pitch and so on. The column for whiff-rate work. |
| `events` | text | Plate-appearance outcome: single, home_run, strikeout, walk, field_out and so on. Populated on completed plate appearances. ⚠️ **Populated only on the final pitch of a plate appearance; NULL on every other pitch.** |
| `bb_type` | code | ground_ball, line_drive, fly_ball, or popup. Populated on balls in play. |
| `hit_location` | int | Fielder position that fielded the ball, 1-9. Populated on balls in play. |
| `hc_x` | pixels | Spray-chart x coordinate in Savant's image space. Populated on balls in play. ⚠️ **Origin is the TOP-LEFT and hc_y increases DOWNWARD. Convert before use: x_ft = (hc_x - 125.42) * 2.0, y_ft = (198.27 - hc_y) * 2.0. Plotting raw produces a vertically mirrored field.** |
| `hc_y` | pixels | Spray-chart y coordinate in Savant's image space. Populated on balls in play. |
| `hit_distance_sc` | feet | Projected distance of the batted ball. Populated on balls in play. Plausible range 0 to 520. |
| `launch_speed` | mph | Exit velocity off the bat. Populated on balls in play. Plausible range 5 to 125. |
| `launch_angle` | degrees | Vertical launch angle. Stored as INTEGER; Savant rounds it. Populated on balls in play. Plausible range -90 to 90. |
| `launch_speed_angle` | int 1-6 | Launch speed/angle zone: 1 weak, 2 topped, 3 under, 4 flare/burner, 5 solid contact, 6 barrel. Populated on balls in play. |
| `hyper_speed` | mph | Adjusted exit velocity: batted balls below 88 mph are set to 88 mph, otherwise the actual exit velocity. Savant's definition, not an inference. ⚠️ **A FLOOR, not a smoothing. It measures top-end contact by discarding the bottom of the distribution, so it is not a substitute for launch_speed in any average.** |

### Expected stats and run values

| Column | Unit | Meaning |
|---|---|---|
| `estimated_ba_using_speedangle` | 0-1 | xBA on contact, from exit velocity and launch angle, plus sprint speed for weakly-hit and topped balls. Populated on balls in play. ⚠️ **Unlike xwOBA, this is still contact-only, verified at zero non-contact rows populated. The classic warning holds: averaging it across all plate appearances drops strikeouts from the numerator while the denominator counts them.** |
| `estimated_woba_using_speedangle` | wOBA scale | xwOBA. In this database it carries PA-ending non-contact events at their linear weight: strikeout 0.000, walk 0.698, HBP 0.729. Populated on completed plate appearances. Plausible range 0 to 2.5. ⚠️ **THE CONVENTION CHANGED. The long-standing public understanding is that this is NULL on strikeouts and walks; in the 2026 data it is populated. So `IS NOT NULL` is not a batted-ball filter -- use type = 'X'. If seasons follow different conventions, code branching on null-ness computes a different statistic per season with no error raised. audit.py checks this per season.** |
| `estimated_slg_using_speedangle` | slg scale | xSLG on contact. Populated on balls in play. |
| `woba_value` | wOBA scale | This event's wOBA numerator contribution: 0 for outs, ~0.70 for a walk, ~2.10 for a home run. Weights drift year to year. |
| `woba_denom` | 0/1 | 1 if the event counts as a wOBA denominator plate appearance. ⚠️ **`WHERE woba_denom = 1` is how you get exactly one row per completed plate appearance.** |
| `babip_value` | 0/1 | BABIP indicator flag. |
| `iso_value` | 0/1 | Isolated-power indicator flag. |
| `delta_run_exp` | runs | Change in run expectancy on this pitch. Plausible range -4 to 4. ⚠️ **From the BATTING team's perspective: positive is good for the hitter, so a strikeout is negative.** |
| `delta_pitcher_run_exp` | runs | The same quantity from the pitcher's perspective, sign inverted. ⚠️ **Using this and delta_run_exp in one model double-counts the same event.** |

### Bat tracking and swing path

The newest and least-exploited columns here. MEASURED availability contradicts the public timeline: bat tracking was announced in May 2024, but this database has it from JULY 2023 -- Savant back-processed the 2023 second half, and the distributions are indistinguishable from later seasons (mean bat speed 69.6 in 2023 versus 69.5 in 2024). That is an extra half-season of swing data most public analysis does not use. Coverage is partial even within a season because the tracking has to see the bat cleanly, so pair any bat-tracking aggregate with an N.

| Column | Unit | Meaning |
|---|---|---|
| `bat_speed` | mph | Barrel speed at contact, or at the nearest point on a swing and miss. *Available from 2023-07.* Populated on swings. Plausible range 20 to 95. ⚠️ **Two artefacts. The maximum is EXACTLY 88.0 in all four seasons, which is a clamp rather than a physical limit -- do not treat the top of the distribution as real. And roughly 0.5% of values fall under 20 mph (minimum 0.3), which are failed reads, not check swings. Filter both tails before computing a player's mean.** |
| `swing_length` | feet | Path length of the barrel through the swing. Longer means more time to react but more distance to cover. *Available from 2023-07.* Populated on swings. Plausible range 2 to 12. |
| `attack_angle` | degrees | Vertical angle at which the sweet spot of the bat travels at the impact point. *Available from 2023-07.* Populated on balls in play. Plausible range -40 to 60. |
| `attack_direction` | degrees | Horizontal angle at which the sweet spot of the bat travels at impact, measured RELATIVE TO CENTER FIELD. *Available from 2023-07.* Populated on balls in play. ⚠️ **Because it is referenced to center field rather than to the pull side, its sign does not flip by batter handedness -- pull for a lefty and pull for a righty land on opposite sides of zero. Flip by `stand` before pooling.** |
| `swing_path_tilt` | degrees | Vertical angular orientation of the swing plane over the 40 ms before contact. *Available from 2023-07.* Populated on balls in play. |
| `intercept_ball_minus_batter_pos_x_inches` | inches | Horizontal distance, in inches, between the intercept point and the batter's centre of mass. *Available from 2023-07.* |
| `intercept_ball_minus_batter_pos_y_inches` | inches | Distance, in inches, from the batter's centre of mass to the intercept point along the mound-to-plate axis. *Available from 2023-07.* |
| `miss_distance` | inches | On a swinging strike, how far the barrel missed the ball. *Available from 2023-07.* Populated on swinging strikes. |

### Age, workload and sequencing

| Column | Unit | Meaning |
|---|---|---|
| `age_pit` | years | Pitcher's age as of 12/31 of the season. |
| `age_bat` | years | Batter's age as of 12/31 of the season. |
| `age_pit_legacy` | years | Pitcher's age as of 6/30. Savant's prior convention, kept for continuity. |
| `age_bat_legacy` | years | Batter's age as of 6/30. Savant's prior convention, kept for continuity. |
| `n_thruorder_pitcher` | int | Times through the order. The times-through-the-order penalty is one of the most robust effects in the data. |
| `n_priorpa_thisgame_player_at_bat` | int | Prior plate appearances this game for this batter. |
| `pitcher_days_since_prev_game` | days | Pitcher's rest. |
| `batter_days_since_prev_game` | days | Batter's rest. |
| `pitcher_days_until_next_game` | days | Days until the pitcher's next game. ⚠️ **Look-ahead. Legitimate for descriptive work, LEAKAGE in any predictive model -- it encodes the future.** |
| `batter_days_until_next_game` | days | Days until the batter's next game. ⚠️ **Look-ahead. Same leakage warning as the pitcher column.** |

### Dead columns

Savant retains these headers and returns nothing. They are stored only because the ingest keeps every column Savant sends.

| Column | Unit | Meaning |
|---|---|---|
| `spin_dir` |  | Retained by Savant, never populated. |
| `spin_rate_deprecated` |  | Retained by Savant, never populated. |
| `break_angle_deprecated` |  | Retained by Savant, never populated. |
| `break_length_deprecated` |  | Retained by Savant, never populated. |
| `tfs_deprecated` |  | Retained by Savant, never populated. |
| `tfs_zulu_deprecated` |  | Retained by Savant, never populated. |
| `sv_id` |  | Non-unique id of the play event within a game. Not populated in this database. |
| `umpire` |  | Retained by Savant, never populated. |

---

## `expected_stats`

One row per player per snapshot, from Savant's expected-statistics leaderboard. This is NOT recomputed from the pitch table -- it is Savant's own season aggregate and will not exactly reconcile with a sum over `pitches`. Minimum 50 PA, set at fetch time.

| Column | Unit | Meaning |
|---|---|---|
| `snapshot_date` | YYYY-MM-DD | When this leaderboard state was captured. A completed season is stamped with its final day; the in-progress season with today. Part of the primary key, which is what lets you watch a gap open over time. |
| `player_type` | code | batter or pitcher. |
| `player_id` | id | MLBAM ID. Joins to pitches.batter / pitches.pitcher. |
| `player_name` | text | Normalised to 'First Last'. |
| `year` | int | Season the leaderboard covers. |
| `pa` | int | Plate appearances, or batters faced for pitchers. |
| `bip` | int | Balls in play. |
| `ba` | 0-1 | Actual batting average. |
| `est_ba` | 0-1 | Expected batting average. |
| `slg` | slg scale | Actual slugging. |
| `est_slg` | slg scale | Expected slugging. |
| `woba` | wOBA scale | Actual wOBA. |
| `est_woba` | wOBA scale | Expected wOBA. The two columns the whole dashboard rests on. |

---

## `batted_ball`

Exit velocity and barrel leaderboard. Minimum 30 batted balls, set at fetch time.

| Column | Unit | Meaning |
|---|---|---|
| `attempts` | int | Batted-ball events. The denominator for everything else here. |
| `avg_hit_speed` | mph | Average exit velocity. |
| `max_hit_speed` | mph | Maximum exit velocity. A skill indicator, but a single-observation one, so noisy. |
| `avg_launch_angle` | degrees | Average launch angle. ⚠️ **An average over a bimodal distribution. Two hitters with identical averages can have completely different distributions.** |
| `barrels` | int | Count of barrels. |
| `brl_percent` | % | Barrels per batted ball. |
| `brl_pa` | % | Barrels per plate appearance. Generally the better of the two -- it does not reward a hitter for avoiding contact. |
| `ev95percent` | % | Hard-hit rate: share of batted balls at 95+ mph. |

---

## `ingest_log`

Fetch bookkeeping. A day absent from this table was never successfully fetched. A failed request is deliberately NOT logged, so a re-run retries it.

| Column | Unit | Meaning |
|---|---|---|
| `scope` | text | Currently always 'pitches'. |
| `day` | YYYY-MM-DD | Day fetched. |
| `rows` | int | Rows stored. 0 means a genuine off-day, recorded so it is never re-requested. |
| `fetched_at` | ISO 8601 | UTC timestamp of the fetch. |

---

## `sprint_speed`

Sprint speed leaderboard: feet per second in a player's fastest one-second window, averaged over roughly his fastest two thirds of opportunities. Fetched fresh each pipeline run rather than backfilled, because it is one small request. This is the one table here that measures the RUNNER rather than the ball, which is exactly why it exists -- the pitch table structurally cannot see it.

| Column | Unit | Meaning |
|---|---|---|
| `snapshot_date` | YYYY-MM-DD | When the leaderboard was captured. |
| `player_id` | id | MLBAM ID. Joins to pitches.batter. |
| `player_name` | text | Normalised to 'First Last'. |
| `year` | int | Season. |
| `age` | years | Player age. |
| `competitive_runs` | int | Qualifying sprint opportunities: two-plus base runs on non-homers, and home-to-first on topped or weakly-hit balls. |
| `bolts` | int | Runs at 30 ft/s or faster. A count of elite-speed events, so it is noisier than the mean. |
| `hp_to_1b` | seconds | Home-to-first time. |
| `sprint_speed` | ft/s | Feet per second. League average is roughly 27; 30+ is elite. Plausible range 20 to 32. |

---

## Derived metrics

Computed in analyze.py and written to output/dashboard_data.json. None come from Savant; all are arguable.

| Metric | Definition | What it assumes |
|---|---|---|
| `luck_gap` | est_woba - woba | That the gap is mostly luck. It is not entirely -- speed and spray tendency create persistent gaps. |
| `luck_z` | luck_gap z-scored against that season's qualified players of the same type | That the gap distribution is roughly normal and that the current season is the right reference population. |
| `outlook` | luck_z for batters, -luck_z for pitchers | Sign normalisation so positive always means 'expect improvement'. |
| `proj_woba_ros` | (est_woba * PA + league_mean * K) / (PA + K), K = 200 batters / 250 pitchers | Marcel-style shrinkage. No aging curve, no park factors, no playing-time forecast, no platoon split. |
| `proj_vs_current` | proj_woba_ros - woba | The size of the implied move. |
| `pct_est_woba / pct_woba` | Percentile rank among qualified players | Qualified players are the right comparison set. |
| `pct_ev / pct_barrel / pct_hardhit` | Contact-quality percentiles from batted_ball | A luck gap without contact-quality support is much more likely to be noise. |
| `qualified` | pa >= 150 | A blunt gate. Metrics stabilise at different rates; one threshold cannot be right for all of them. |
| `flagged` | qualified AND abs(luck_z) >= 1.5 | About 13% of players by construction, so the list is never empty -- including in a season where nothing interesting happened. |
| `sprint_speed` | joined from the sprint_speed table, batters only | That a pitcher's own speed is irrelevant to the hitters he faces, so pitcher rows are left null. |
| `luck_gap_adj` | luck_gap minus the part predicted by a linear fit of luck_gap on sprint_speed, re-centred | That the speed-explained part of the gap is skill, not luck. Fitted per run; the coefficient and R-squared are written into the payload so the assumption can be checked rather than trusted. |
| `luck_z_adj` | luck_gap_adj z-scored against qualified players of the same type | Same as luck_z, on the speed-residualised gap. |
| `outlook_adj` | luck_z_adj for batters, -luck_z_adj for pitchers | Reported ALONGSIDE outlook, never replacing it. Which one predicts better is a question for regression_test.py, not an assumption. |
| `pct_sprint` | Sprint-speed percentile among qualified batters | Context for reading a flagged player -- a fast player near the top of this column is the classic false positive the raw luck gap produces. |

---

## The five gotchas most likely to produce a wrong answer

1. The strike zone changes definition in 2026 (operator-set through 2025, ABS-defined after). Any zone-based metric computed across 2025 and 2026 is comparing two different instruments.
2. `player_name` is the PITCHER. Join on batter / pitcher IDs, never on the name column.
3. xwOBA and xBA disagree about non-contact events. In this data xwOBA carries strikeouts and walks at their linear weight; xBA does not. Filter contact with `type = 'X'`, never with a null check, and confirm the convention is the same in every season you pool.
4. `game_type` includes spring training and postseason. Filter to 'R'.
5. Handedness sign conventions on `pfx_x` and `plate_x` will silently cancel effects if you pool without flipping.
6. Cross-season discontinuities that are not trends: sweeper classification arrives in 2023, shift restrictions change in 2023, bat tracking arrives mid-2024, swing path in 2025. Any 2023-2026 series has to be read with those breakpoints in mind.

---

## How this file stays honest

Every warning above that could be checked against data has been. The xwOBA non-contact finding was not known when this file was first drafted -- it came out of `audit.py` failing an integrity check that asserted the textbook behaviour, against the actual database. That is the intended workflow: assertions in the audit, corrections in the schema, neither one taken on trust.

Re-run `python3 audit.py` after every backfill. If an integrity check fails, the schema is wrong until proven otherwise, not the data. A column that appears in the database but not in `schema.yaml` is reported by the audit as undocumented rather than passing through unnoticed.


<!-- make_dictionary.py from schema.yaml -- edit the YAML, not the markdown -->
