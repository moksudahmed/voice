# =========================================================
# APP
# =========================================================
async def scrap_page(page):
    return await page.evaluate(r"""
        () => {

            const clean = (t) =>
                (t || "")
                    .replace(/\s+/g, " ")
                    .trim();

            const safeText = (selector) => {
                const el = document.querySelector(selector);
                return el ? clean(el.innerText) : "";
            };

            const safeImg = (selector) => {
                const el = document.querySelector(selector);
                return el ? el.src : "";
            };

            const data = {
                team_a: "",
                team_b: "",
                score: "",
                overs: "",
                balls: 0,
                crr: "",
                status: "",
                commentary: "",
                batting: "",

                bowler: "",
                bowler_fig: "",
                bowler_img: "",

                striker: "",
                striker_runs: "",
                striker_balls: "",
                striker_full: "",
                striker_img: "",

                non_striker: "",
                non_striker_runs: "",
                non_striker_balls: "",
                non_striker_full: "",
                non_striker_img: "",

                partnership: "",
                last_wicket: "",

                overs_timeline: [],
                result_boxes: [],

                target: "",

                live_players: {
                    batsmen: [],
                    bowler: null
                },

                updated: Date.now()
            };

            const bodyText = clean(document.body.innerText);

            // SCORE + OVERS
            const scoreOverMatch = bodyText.match(
                /(\d{1,3})\s*[-/]\s*(\d{1,2})\s*\(?(\d+)\.(\d)\)?/
            );

            if (scoreOverMatch) {
                const runs = parseInt(scoreOverMatch[1]);
                const wickets = parseInt(scoreOverMatch[2]);
                const over = parseInt(scoreOverMatch[3]);
                const ball = parseInt(scoreOverMatch[4]);

                data.score = `${runs}/${wickets}`;
                data.overs = `${over}.${ball}`;
                data.balls = (over * 6) + ball;
            }

            // CRR
            const crrMatch = bodyText.match(
                /CRR\s*:?\s*(\d+\.\d+)/i
            );

            if (crrMatch) {
                data.crr = crrMatch[1];
            }

            // STATUS
            const statusMatch = bodyText.match(
                /(LIVE|Match Info|Stumps|Innings Break|Opt to Bat|Won by.*)/i
            );

            if (statusMatch) {
                data.status = clean(statusMatch[1]);
            }

            // BATTING TEAM
            const teamBlocks = document.querySelectorAll(".team-content");

            if (teamBlocks.length >= 1) {
                const team1Name =
                    teamBlocks[0].querySelector(".team-name");

                if (team1Name) {
                    data.batting = clean(team1Name.innerText);
                }
            }

            // PARTNERSHIP
            const partnershipMatch = bodyText.match(
                /(\d+)\((\d+)\)/
            );

            if (partnershipMatch) {
                data.partnership =
                    `${partnershipMatch[1]}(${partnershipMatch[2]})`;
            }

            // LAST WICKET
            const wicketMatch = bodyText.match(
                /Last Wkt\s*:?\s*(.*)/i
            );

            if (wicketMatch) {
                data.last_wicket = clean(wicketMatch[1]);
            }

            // RESULT BOXES
            document.querySelectorAll(".result-box").forEach(el => {
                const txt = clean(el.innerText);

                if (txt) {
                    data.result_boxes.push(txt);
                }
            });

            // PLAYER SECTION
            const playerSection =
                document.querySelector(".player-profile");

            if (playerSection) {

                const batsmenCards =
                    playerSection.querySelectorAll(
                        ".batsmen-partnership"
                    );

                batsmenCards.forEach(card => {

                    if (card.querySelector(".batsmen-score.bowler"))
                        return;

                    const img =
                        card.querySelector(".batsmen-image img");

                    const name =
                        card.querySelector(".batsmen-name p");

                    const scorePs =
                        card.querySelectorAll(".batsmen-score p");

                    let runs = "";
                    let balls = "";

                    if (scorePs.length >= 2) {
                        runs = clean(scorePs[0].innerText);
                        balls = clean(scorePs[1].innerText)
                            .replace(/[()]/g, "");
                    }

                    data.live_players.batsmen.push({
                        name: name ? clean(name.innerText) : "",
                        runs,
                        balls,
                        image: img ? img.src : ""
                    });
                });

                const bowlerCard =
                    [...batsmenCards].find(card =>
                        card.querySelector(".batsmen-score.bowler")
                    );

                if (bowlerCard) {

                    const bowlerImg =
                        bowlerCard.querySelector(
                            ".batsmen-image img"
                        );

                    const bowlerName =
                        bowlerCard.querySelector(
                            ".batsmen-name p"
                        );

                    const figures =
                        bowlerCard.querySelectorAll(
                            ".batsmen-score.bowler p"
                        );

                    let fig = "";

                    if (figures.length >= 2) {
                        fig =
                            clean(figures[0].innerText) +
                            " " +
                            clean(figures[1].innerText);
                    }

                    data.live_players.bowler = {
                        name: bowlerName
                            ? clean(bowlerName.innerText)
                            : "",
                        figures: fig,
                        image: bowlerImg
                            ? bowlerImg.src
                            : ""
                    };
                }
            }

            // STRIKER
            if (data.live_players.batsmen.length >= 1) {
                const s = data.live_players.batsmen[0];

                data.striker = s.name;
                data.striker_runs = s.runs;
                data.striker_balls = s.balls;
                data.striker_full =
                    `${s.name} ${s.runs} (${s.balls})`;
                data.striker_img = s.image;
            }

            // NON STRIKER
            if (data.live_players.batsmen.length >= 2) {
                const ns = data.live_players.batsmen[1];

                data.non_striker = ns.name;
                data.non_striker_runs = ns.runs;
                data.non_striker_balls = ns.balls;
                data.non_striker_full =
                    `${ns.name} ${ns.runs} (${ns.balls})`;
                data.non_striker_img = ns.image;
            }

            // BOWLER
            if (data.live_players.bowler) {
                data.bowler =
                    data.live_players.bowler.name;

                data.bowler_fig =
                    data.live_players.bowler.figures;

                data.bowler_img =
                    data.live_players.bowler.image;
            }

            // OVERS TIMELINE
            document.querySelectorAll(".overs-slide")
                .forEach(overEl => {

                    const overData = {
                        over: "",
                        balls: [],
                        total: ""
                    };

                    const overTitle =
                        overEl.querySelector("span");

                    if (overTitle) {
                        overData.over =
                            clean(overTitle.innerText);
                    }

                    overEl.querySelectorAll(".over-ball")
                        .forEach(ball => {

                            const val =
                                clean(ball.innerText);

                            if (val)
                                overData.balls.push(val);
                        });

                    const total =
                        overEl.querySelector(".total");

                    if (total) {
                        overData.total =
                            clean(
                                total.innerText.replace("=", "")
                            );
                    }

                    data.overs_timeline.push(overData);
                });

            // TARGET
            const finalResultEl =
                document.querySelector(
                    ".final-result.m-none"
                );

            if (finalResultEl) {

                const resultText =
                    clean(finalResultEl.innerText);

                if (resultText) {
                    data.target = resultText;
                }
            }

            return data;
        }
    """)

async def scrap_page_old(page):
    return await page.evaluate("""
            () => {

                // =================================================
                // HELPERS
                // =================================================

                const clean = (t) =>
                    (t || "")
                        .replace(/\\s+/g, " ")
                        .trim();

                const safeText = (selector) => {

                    const el = document.querySelector(selector);

                    return el
                        ? clean(el.innerText)
                        : "";
                };

                const safeImg = (selector) => {

                    const el = document.querySelector(selector);

                    return el
                        ? el.src
                        : "";
                };

                // =================================================
                // DATA OBJECT
                // =================================================

                const data = {

                    // MATCH
                    team_a: "",
                    team_b: "",

                    score: "",
                    overs: "",
                    crr: "",

                    status: "",
                    commentary: "",
                    batting:"",                            

                    // BOWLER
                    bowler: "",
                    bowler_fig: "",
                    bowler_img: "",

                    // STRIKER
                    striker: "",
                    striker_runs: "",
                    striker_balls: "",
                    striker_full: "",
                    striker_img: "",

                    // NON STRIKER
                    non_striker: "",
                    non_striker_runs: "",
                    non_striker_balls: "",
                    non_striker_full: "",
                    non_striker_img: "",

                    // EXTRA
                    partnership: "",
                    last_wicket: "",

                    // TIMELINE
                    overs_timeline: [],

                    // RESULT
                    result_boxes: [],
                                         
                    //Target Run
                    target: "",

                    // PLAYERS
                    live_players: {
                        batsmen: [],
                        bowler: null
                    },

                    updated: Date.now()
                };

                // =================================================
                // BODY TEXT
                // =================================================

                const bodyText =
                    clean(document.body.innerText);

                // =================================================
                // TEAM NAMES
                // =================================================

                /*const teamMatch =
                    bodyText.match(
                        /([A-Za-z\\s\\-]+)\\s+vs\\s+([A-Za-z\\s\\-]+)/i
                    );

                if (teamMatch) {

                    data.team_a =
                        clean(teamMatch[1]);

                    data.team_b =
                        clean(teamMatch[2]);
                }*/

                // =================================================
                // SCORE + OVERS
                // Example:
                // 147-2 (14.2)
                // 147/2 14.2
                // =================================================

                const scoreOverMatch = bodyText.match(
                    /(\d{1,3})\s*[-/]\s*(\d{1})\s*(\d+)\.(\d)/
                );

                if (scoreOverMatch) {

                    const runs = parseInt(scoreOverMatch[1]);      // 86
                    const wickets = parseInt(scoreOverMatch[2]);   // 1
                    const over = parseInt(scoreOverMatch[3]);      // 8
                    const ball = parseInt(scoreOverMatch[4]);      // 5

                    data.score = `${runs}/${wickets}`;

                    // keep CREX-style overs format
                    data.overs = `${over}.${ball}`;

                    // optional: total balls (VERY IMPORTANT for logic)
                    data.balls = (over * 6) + ball;
                }
                // =================================================
                // CRR
                // =================================================

                const crrMatch =
                    bodyText.match(
                        /CRR\\s*:?\\s*(\\d+\\.\\d+)/i
                    );

                if (crrMatch) {

                    data.crr =
                        crrMatch[1];
                }

                // =================================================
                // STATUS
                // =================================================

                const statusMatch =
                    bodyText.match(
                        /(LIVE|Match Info|Stumps|Innings Break|Opt to Bat|Won by.*)/i
                    );

                if (statusMatch) {

                    data.status =
                        clean(statusMatch[1]);
                }

                // =================================================
                // COMMENTARY
                // =================================================

               /* const commentaryEl =
                    document.querySelector(
                        ".commentary-text, .live-commentary, .commentary"
                    );

                if (commentaryEl) {

                    data.commentary =
                        clean(commentaryEl.innerText);
                }*/

                const teamBlocks =
                    document.querySelectorAll(
                    ".team-content"
                    );

                    // TEAM A
                    if (teamBlocks.length >= 1) {

                    const team1 = teamBlocks[0];

                    const team1Name =
                        team1.querySelector(".team-name");
                    

                    if (team1Name) {

                        data.batting =
                            clean(team1Name.innerText);
                    }                    

                    }
                    
                // =================================================
                // PARTNERSHIP
                // =================================================

                const partnershipMatch =
                    bodyText.match(
                        /(\\d+)\\((\\d+)\\)/
                    );

                if (partnershipMatch) {

                    data.partnership =
                        `${partnershipMatch[1]}(${partnershipMatch[2]})`;
                }

                // =================================================
                // LAST WICKET
                // =================================================

                const wicketMatch =
                    bodyText.match(
                        /Last Wkt\\s*:??\\s*(.*)/i
                    );

                if (wicketMatch) {

                    data.last_wicket =
                        clean(wicketMatch[1]);
                }

                // =================================================
                // RESULT BOXES
                // =================================================

                document
                    .querySelectorAll(".result-box")
                    .forEach(el => {

                        const txt =
                            clean(el.innerText);

                        if (txt) {

                            data.result_boxes.push(txt);
                        }
                    });

                // =================================================
                // LIVE PLAYER SECTION
                // =================================================

                const playerSection =
                    document.querySelector(
                        ".player-profile"
                    );

                if (playerSection) {

                    // =============================================
                    // BATSMEN
                    // =============================================

                    const batsmenCards =
                        playerSection.querySelectorAll(
                            ".batsmen-partnership"
                        );

                    batsmenCards.forEach(card => {

                        // Skip bowler card
                        if (
                            card.querySelector(
                                ".batsmen-score.bowler"
                            )
                        ) {
                            return;
                        }

                        const img =
                            card.querySelector(
                                ".batsmen-image img"
                            );

                        const name =
                            card.querySelector(
                                ".batsmen-name p"
                            );

                        const scorePs =
                            card.querySelectorAll(
                                ".batsmen-score p"
                            );

                        let runs = "";
                        let balls = "";

                        if (scorePs.length >= 2) {

                            runs =
                                clean(scorePs[0].innerText);

                            balls =
                                clean(scorePs[1].innerText)
                                    .replace(/[()]/g, "");
                        }

                        data.live_players.batsmen.push({

                            name: name
                                ? clean(name.innerText)
                                : "",

                            runs: runs,

                            balls: balls,

                            image: img
                                ? img.src
                                : ""
                        });
                    });

                    // =============================================
                    // BOWLER
                    // =============================================

                    const bowlerCard =
                        playerSection.querySelector(
                            ".batsmen-partnership:has(.batsmen-score.bowler)"
                        );

                    if (bowlerCard) {

                        const bowlerImg =
                            bowlerCard.querySelector(
                                ".batsmen-image img"
                            );

                        const bowlerName =
                            bowlerCard.querySelector(
                                ".batsmen-name p"
                            );

                        const figures =
                            bowlerCard.querySelectorAll(
                                ".batsmen-score.bowler p"
                            );

                        let fig = "";

                        if (figures.length >= 2) {

                            fig =
                                clean(figures[0].innerText) +
                                " " +
                                clean(figures[1].innerText);
                        }

                        data.live_players.bowler = {

                            name: bowlerName
                                ? clean(bowlerName.innerText)
                                : "",

                            figures: fig,

                            image: bowlerImg
                                ? bowlerImg.src
                                : ""
                        };
                    }
                }

                // =================================================
                // STRIKER
                // =================================================

                if (
                    data.live_players.batsmen.length >= 1
                ) {

                    const s =
                        data.live_players.batsmen[0];

                    data.striker =
                        s.name;

                    data.striker_runs =
                        s.runs;

                    data.striker_balls =
                        s.balls;

                    data.striker_full =
                        `${s.name} ${s.runs} (${s.balls})`;

                    data.striker_img =
                        s.image;
                }

                // =================================================
                // NON STRIKER
                // =================================================

                if (
                    data.live_players.batsmen.length >= 2
                ) {

                    const ns =
                        data.live_players.batsmen[1];

                    data.non_striker =
                        ns.name;

                    data.non_striker_runs =
                        ns.runs;

                    data.non_striker_balls =
                        ns.balls;

                    data.non_striker_full =
                        `${ns.name} ${ns.runs} (${ns.balls})`;

                    data.non_striker_img =
                        ns.image;
                }

                // =================================================
                // BOWLER
                // =================================================

                if (data.live_players.bowler) {

                    data.bowler =
                        data.live_players.bowler.name;

                    data.bowler_fig =
                        data.live_players.bowler.figures;

                    data.bowler_img =
                        data.live_players.bowler.image;
                }

                // =================================================
                // OVERS TIMELINE
                // =================================================

                document
                    .querySelectorAll(".overs-slide")
                    .forEach(overEl => {

                        const overData = {

                            over: "",
                            balls: [],
                            total: ""
                        };

                        // OVER TITLE

                        const overTitle =
                            overEl.querySelector("span");

                        if (overTitle) {

                            overData.over =
                                clean(overTitle.innerText);
                        }

                        // BALLS

                        overEl
                            .querySelectorAll(".over-ball")
                            .forEach(ball => {

                                const val =
                                    clean(ball.innerText);

                                if (val) {

                                    overData.balls.push(val);
                                }
                            });

                        // TOTAL

                        const total =
                            overEl.querySelector(".total");

                        if (total) {

                            overData.total =
                                clean(
                                    total.innerText.replace("=", "")
                                );
                        }

                        data.overs_timeline.push(overData);
                    });

                                         

                    // =================================================
                    // RESULT / MATCH STATUS
                    // =================================================

                    // final result text
                    const finalResultEl =
                        document.querySelector(
                            ".final-result.m-none"
                        );

                    if (finalResultEl) {

                        const resultText =
                            clean(finalResultEl.innerText);

                        if (resultText) {

                            // main status
                            //data.status = resultText;

                            // separate field
                            data.target = resultText;

                            // push to result boxes
                            //data.result_boxes.push(resultText);
                        }
                    }
                // =================================================
                // RETURN
                // =================================================

                return data;
            }
            """)

