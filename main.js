'use strict';

// TODO start/stop recording buttons
// TODO fix styling of LLM window
// TODO collapse button for transcript

let socket;
let audioContext, mediaRecorder, silenceTimer;
let audioChunks = [];
const transcriptDiv = document.getElementById('transcript');
const llmDiv = document.getElementById('llm-responses');
const restartButton = document.getElementById('restart');
let isConnected = false;
let isRecording = false;

function startWebSocket() {
    socket = new WebSocket('ws://10.35.20.13:8765');
    isConnected = true;
    activateRecBtn.disabled = false;

    socket.onclose = () => {
        isConnected = false;
    };

    socket.onmessage = event => {
        try {
            const msg = JSON.parse(event.data);
            if (msg.data == "") {
                return;
            }
            if (msg.type === 'transcript') {
                const transcriptParagraph = document.createElement('p');
                transcriptParagraph.textContent = msg.data;
                transcriptDiv.appendChild(transcriptParagraph);
                transcriptDiv.scrollTop = transcriptDiv.scrollHeight;
            } else if (msg.type === 'llm') {
                const llmParagraph = document.createElement('p');
                llmParagraph.textContent = msg.data;
                llmDiv.appendChild(llmParagraph);
                llmDiv.scrollTop = llmDiv.scrollHeight;
            }
        } catch (error) {
            console.error("Invalid message received:", event.data);
        }

        console.log("Started websocket");
    };
}

function closeSocket() {
    if (socket) {
        socket.close();
        isConnected = false;
        isRecording = false;
    }
}

function startRecording() {
    if (!isConnected) {
        console.log("Cannot start recording; no websocket connection");
        return;
    }

    if (isRecording) {
        console.log("startRecording called when isRecording is true");
        return;
    }

    navigator.mediaDevices.getUserMedia({ audio: true }).then(stream => {
        isRecording = true;

        audioContext = new window.AudioContext();
        const source = audioContext.createMediaStreamSource(stream);
        const analyser = audioContext.createAnalyser();
        source.connect(analyser);
        analyser.fftSize = 512;

        const dataArray = new Uint8Array(analyser.frequencyBinCount);

        function checkSilence() {
            analyser.getByteFrequencyData(dataArray);
            let sum = dataArray.reduce((a, b) => a + b, 0);
            let average = sum / dataArray.length;
            return average < 5; // Threshold for silence detection
        }

        mediaRecorder = new MediaRecorder(stream);
        mediaRecorder.ondataavailable = event => audioChunks.push(event.data);

        mediaRecorder.onstop = () => {
            if (isConnected) {
                const audioBlob = new Blob(audioChunks, { type: 'audio/webm' });
                socket.send(audioBlob);
            }
            audioChunks = [];
        };

        function processAudio() {
            if (!isConnected || !isRecording) {
                mediaRecorder.stop();
                stream.getTracks().forEach(track => track.stop());
                return;
            }

            if (checkSilence()) {
                if (!silenceTimer) {
                    silenceTimer = setTimeout(() => {
                        if (mediaRecorder.state !== 'inactive') {
                            mediaRecorder.stop();
                        }
                        silenceTimer = null;
                    }, 1000); // 1 second silence detection
                }
            } else {
                if (silenceTimer) {
                    clearTimeout(silenceTimer);
                    silenceTimer = null;
                }
                if (mediaRecorder.state === 'inactive') {
                    audioChunks = [];
                    mediaRecorder.start();
                }
            }
            requestAnimationFrame(processAudio);
        }

        processAudio();
    }).catch(console.error);
}

function stopRecording() {
    isRecording = false;
}

activateConnBtn.addEventListener('click', () => {
    closeSocket();
    startWebSocket();
});

activateRecBtn.addEventListener('click', () => {
    if (activateRecBtn.getAttribute('data-isrecording') == true) {
        stopRecording();
        activateRecBtn.innerText = 'Start recording';
    } else {
        startRecording();
        activateRecBtn.innerText = 'Pause recording';
    }
});