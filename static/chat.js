// Function to send a message
function sendMessage() {
    var messageInput = document.getElementById('user-input');
    // var selectedMode = document.querySelector('input[name="chat_mode"]:checked').value; // Get selected chat mode

    // Trim whitespace from the message
    var trimmedMessage = messageInput.value.trim();

    if (trimmedMessage === '') return; // If message is empty, do nothing

    // Display user message on the right side
    updateChat(trimmedMessage, 'user');

    // Clear the message input
    messageInput.value = '';

    // Simulate bot response with the user message
    simulateBotResponse(trimmedMessage);
}

// Function to simulate bot response
function simulateBotResponse(userQuery) {
    // Simulate delay to mimic server response time
    setTimeout(() => {
        // Send the user query and mode to the server
        fetch('/get_bot_response', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ query: userQuery}), // Pass the user query and mode
        })
        .then(response => response.json())
        .then(data => {
            // Extract the bot response from the data
            var botResponse = data.bot_response;

            // Display bot response on the left side
            updateChat(botResponse, 'bot');
        })
        .catch(error => {
            console.error('Error fetching bot response:', error);
        });
    }, 1000); // Adjust delay time as needed
}

// Function to update chat with the received response
function updateChat(message, sender) {
    // Only proceed if message is not empty
    if (message.trim() === '') return;

    // Create a new chat bubble
    var bubble = document.createElement('div');
    bubble.classList.add('message');

    // Determine the class for the chat bubble based on the sender
    var bubbleClass = sender === 'user' ? 'right' : 'left';

    // Add the appropriate class to the chat bubble
    bubble.classList.add(bubbleClass);

    // Add the message to the chat bubble
    bubble.innerHTML = `<div class="message-content"><p>${message}</p></div>`;

    // Append the chat bubble to the chat section
    var chatSection = document.querySelector('.chart-section');
    chatSection.appendChild(bubble);

    // Scroll to the bottom of the chat section
    chatSection.scrollTop = chatSection.scrollHeight;
}

// Event listener for the send button
document.querySelector('.bxs-send').addEventListener('click', function() {
    sendMessage();
});

// Event listener for the textarea to send message on Enter key press
document.getElementById('user-input').addEventListener('keypress', function(e) {
    if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault(); // Prevent default behavior (inserting newline)
        sendMessage();
    }
});

// Function to initialize SpeechRecognition
function initSpeechRecognition() {
    // Check if SpeechRecognition is supported by the browser
    if ('SpeechRecognition' in window || 'webkitSpeechRecognition' in window) {
        // Create a new SpeechRecognition instance
        const recognition = new (window.SpeechRecognition || window.webkitSpeechRecognition)();

        // Set properties for recognition
        recognition.lang = 'en-US'; // Set language to English
        recognition.interimResults = false; // Disable interim results

        // When speech recognition starts
        recognition.onstart = function() {
            console.log('Speech recognition started...');
        };

        // When speech recognition ends
        recognition.onend = function() {
            console.log('Speech recognition ended.');
        };

        // When speech is recognized
        recognition.onresult = function(event) {
            const query = event.results[0][0].transcript.trim(); // Get recognized speech
            console.log('Recognized query:', query);
            sendMessage(query); // Send the query as a message
        };

        // Add event listener to the microphone button
        const micButton = document.getElementById('micButton');
        micButton.addEventListener('click', function() {
            // Start speech recognition
            recognition.start();
        });
    } else {
        console.error('Speech recognition is not supported by this browser.');
    }
}

// Initialize speech recognition when the DOM content is loaded
document.addEventListener('DOMContentLoaded', function() {
    initSpeechRecognition();
});
