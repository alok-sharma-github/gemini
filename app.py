from flask import Flask, render_template, jsonify, request
import shopify
import os
import re
from llama_index.core import Settings
from llama_index.llms.gemini import Gemini
from llama_index.embeddings.huggingface import HuggingFaceEmbedding
from llama_index.core.callbacks import CallbackManager
from llama_index.core import VectorStoreIndex, SimpleDirectoryReader
from llama_index.core import PromptTemplate
import markdown
import bleach
from bs4 import BeautifulSoup
app = Flask(__name__)

os.environ['GOOGLE_API_KEY'] = "AIzaSyD0yxW9VEXUBW_YBJb96eP6yQ_-sum1F9U"
# Set environment variable for Google API key
os.environ['GOOGLE_API_KEY'] = os.getenv('GOOGLE_API_KEY')

# Safety settings for LLM
safety_settings = [
    {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
    {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
    {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
    {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
]

# Generation configuration for LLM
generation_config = {
    "temperature": 0.2,
    "top_p": 0.9,
    "top_k": 50,
    "max_output_tokens": 8024,
}

# Initialize LLM with generation configuration and safety settings
llm = Gemini(
    model_types="gemini-1.5-Pro",
    generation_config=generation_config,
    safety_settings=safety_settings,
    device='cuda',
    device_map='cuda'
)
Settings.llm = llm

# Embedding model
model_name = "nomic-ai/nomic-embed-text-v1"
embed_model = HuggingFaceEmbedding(model_name=model_name, trust_remote_code=True, device='cuda')
Settings.embed_model = embed_model

# Prompt template for LLM
template = (
    "I have provided context information below.\n"
    "---------------------\n"
    "{context_str}"
    "\n---------------------\n"
    "You are a conversational AI.\n"
    "If the user greets with 'Hi', 'Hello', 'Hey', or similar, respond with a greeting and ask how you can assist them.\n"
    "Otherwise, use the following response format for product-related queries:\n"
    "Response Format: Bullet points with key-value pairs and product name as Title.\n"
    '''*Sample Response Format:
        - Title: Title of products.\n'''
    "Use only the provided context, no external knowledge allowed. {query_str}\n\n"
)
llm_prompt = PromptTemplate(template)

# Load documents and build index
documents = SimpleDirectoryReader("data").load_data()
index = VectorStoreIndex.from_documents(documents)

# Create query and chat engines
#query_engine = index.as_query_engine(text_qa_template=llm_prompt, similarity_top_k=15)
chat_engine = index.as_chat_engine(text_qa_template=llm_prompt, chat_mode="condense_question",verbose=True,max_output_tokens=8024)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/get_bot_response', methods=['POST'])
def get_bot_response():
    user_query = request.json.get('query')
    mode =intent(user_query)
    # if not user_query or not mode:
    #     return jsonify({'bot_response': 'Invalid input.'}), 400

    
    product_info, chat_response = query_product_info(user_query)
    formatted_chat_response = format_chat_response(chat_response)
    if mode == 'recommendation':
        bot_response = generate_bot_response(product_info, formatted_chat_response)
    elif mode =='conversation':
        bot_response = generate_bot_response(product_info=None, chat_response=formatted_chat_response)
    return jsonify({'bot_response': bot_response})         

    # except Exception as e:
    #     return jsonify({'bot_response': f'Error: {str(e)}'}), 500

def create_shopify_session(shop_url, api_version, admin_api_key):
    try:
        session = shopify.Session(shop_url, api_version, admin_api_key)
        shopify.ShopifyResource.activate_session(session)
        return session
    except Exception as e:
        print("Error activating Shopify session:", e)
        return None

def intent(user_query):
    intent_prompt=f'''You are an AI designed to identify the intent behind user queries. Your task is to determine whether the user is looking for a conversation or a recommendation. If the user is engaging in a discussion, seeking opinions, sharing information, asking about a product, or inquiring about specifications or details of products, classify it as "conversation." If the user is asking for advice, suggestions, or specific information not related to product details, classify it as "recommendation." Respond with one word only: either "conversation" or "recommendation."

Examples:

User: "What do you think about the latest Marvel movie?"
AI: conversation

User: "Can you suggest a good restaurant in New York?"
AI: recommendation

User: "How have you been?"
AI: conversation

User: "What's the best way to learn Python programming?"
AI: recommendation

User: "Tell me about this product."
AI: conversation

User: "What are the specifications of this product?"
AI: conversation

Now, analyze the following user query and respond appropriately:

User: "{user_query}"
'''

    resp=llm.complete(intent_prompt)
    return resp.text


def deactivate_shopify_session():
    try:
        shopify.ShopifyResource.clear_session()
    except Exception as e:
        print("Error deactivating Shopify session:", e)

def get_chat_response(prompt):
    # Convert the prompt to lowercase once and use it for comparison
    lower_prompt = prompt.lower()

    # Check if the prompt is "hi" or "hello"
    if lower_prompt not in {"hi", "hello", "restart","reset"}:
        try:
            response = chat_engine.chat(prompt).response
            print("Response:\n", response)
            return response
        except Exception as e:
            print("Error getting response from chat engine:", e)
            return ""
    else:
        chat_engine.reset()
        return "By typing Hi or Hello, you just cleared the chat-history. Now you can start a fresh chat."


def extract_product_titles(response):
    pattern = r'Title: (.*)'
    return re.findall(pattern, response)

def find_product_images(shop_url, title):
    try:
        products = shopify.Product.find(title=title)
        if products:
            for product in products:
                image_src = product.images[0].src if product.images else None
                product_url = f"{shop_url}/products/{product.handle}"
                if image_src:
                    return {"product_url": product_url, "image_src": image_src}
                else:
                    print("No image found for product:", product.title)
        else:
            print("No products found with the title:", title)
    except Exception as e:
        print(f"Error finding products with title {title}:", e)
    return None

def query_product_info(prompt):
    shop_url = 'https://boatai.myshopify.com/'
    admin_api_key = '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'
    api_version = "2023-10"
    # shop_url = 'https://shopingai.myshopify.com/'
    # admin_api_key = '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'
    # api_version = "2023-10"

    session = create_shopify_session(shop_url, api_version, admin_api_key)
    if not session:
        return {}, ""

    response = get_chat_response(prompt)
    if not response:
        deactivate_shopify_session()
        return {}, ""

    product_titles = extract_product_titles(response)
    product_images = {}

    for title in product_titles:
        print("Title:", title)
        product_image_info = find_product_images(shop_url, title)
        if product_image_info:
            product_images[title] = product_image_info

    deactivate_shopify_session()
    return product_images, response

def generate_bot_response(product_info, chat_response):
    response = ""

    if product_info:
        response += "<div class='message-final'>"
        #response += f"<h3>{chat_response}</h3>"
        response += "<div class='product-container' style='display: flex; overflow-x: auto; white-space: nowrap;'>"

        for product, info in product_info.items():
            product_url = info.get('product_url', 'Not available')
            image_src = info.get('image_src', 'Not available')

            response += "<div class='product-item' style='flex: 0 0 auto; margin-right: 20px;'>"
            response += f"<h4><a href='{product_url}' target='_blank'>{product}</a></h4>"
            response += f"<a href='{product_url}' target='_blank'><img src='{image_src}' alt='{product}' style='max-width: 200px;'></a>"
            response += "</div>"

        response += "</div>"
        response += "</div>"
    else:
        response += f"<p>{chat_response}</p>"

    return response

def format_chat_response(chat_response):
    # Remove Markdown characters and format for HTML
    html_response = markdown.markdown(chat_response, extensions=['extra', 'sane_lists'])
    # Remove <p> tags by parsing with BeautifulSoup and reconstructing the HTML without <p> tags
    soup = BeautifulSoup(html_response, "html.parser")
    # Remove <p> tags and keep their contents
    for p_tag in soup.find_all('p'):
        p_tag.unwrap()  # Removes the <p> tag but keeps its content
    # Get the cleaned HTML
    clean_html_response = str(soup)
    # Configuration for bleach
    allowed_tags = [
        'em', 'strong', 'ul', 'li'
    ]
    # Sanitize the HTML with custom configuration
    clean_html_response = bleach.clean(
        clean_html_response,
        tags=allowed_tags,
        attributes={},  # No special attributes needed
    )

    return clean_html_response

if __name__ == "__main__":
    app.run(debug=True)
