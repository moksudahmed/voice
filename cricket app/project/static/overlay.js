const ws = new WebSocket("ws://" + location.host + "/ws");

ws.onmessage = (event) => {
    const d = JSON.parse(event.data);

    document.getElementById("score").innerText = d.score;
    document.getElementById("overs").innerText = d.overs;

    let box = document.getElementById("overBox");
    box.innerHTML = "";

    d.this_over.forEach(ball => {
        let el = document.createElement("div");
        el.classList.add("ball");

        if (ball == "4") el.classList.add("b4");
        else if (ball == "6") el.classList.add("b6");
        else if (ball == "W") el.classList.add("bW");

        el.innerText = ball;
        box.appendChild(el);
    });
};