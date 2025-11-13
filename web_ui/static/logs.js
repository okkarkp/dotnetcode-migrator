let socket = new WebSocket("ws://" + window.location.host + "/ws/logs");
let box = document.getElementById("logbox");

socket.onmessage = function(event) {
    box.textContent += event.data + "\n";
    box.scrollTop = box.scrollHeight;
};
