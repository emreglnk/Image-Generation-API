import os
import io
import requests
import replicate
from fastapi import FastAPI, Header, HTTPException, Security, Request
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from openai import OpenAI
from rembg import remove
from PIL import Image, ImageColor
from fastapi.responses import StreamingResponse

app = FastAPI()

# --- SECURITY AND CONFIGURATION ---
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Environment Variables
REPLICATE_API_TOKEN = os.getenv("REPLICATE_API_TOKEN")
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
API_SECRET_KEY = os.getenv("API_SECRET_KEY")
ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "*").split(",")

# AI Configuration
AI_SYSTEM_PROMPT = os.getenv("AI_SYSTEM_PROMPT", "You are a food photography prompt engineer. Describe the food item for Flux AI. KEYWORDS: Top-down view, Isolated on White Background, Studio Lighting, Minimalist. Output ONLY the prompt.")
AI_FALLBACK_PROMPT = os.getenv("AI_FALLBACK_PROMPT", "Professional food photo of {product_name}, isolated on white background.")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Token Verification
async def verify_token(x_access_token: str = Header(...)):
    if x_access_token != API_SECRET_KEY:
        raise HTTPException(status_code=403, detail="Access Denied: Invalid Key")
    return x_access_token

# --- AI LOGIC ---

def get_deepseek_prompt(product_name, style_instruction):
    if not DEEPSEEK_API_KEY:
        return AI_FALLBACK_PROMPT.format(product_name=product_name)
    
    client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url="https://api.deepseek.com/v1")
    try:
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": AI_SYSTEM_PROMPT},
                {"role": "user", "content": f"Describe: {product_name}. Style Requirement: {style_instruction}"}
            ]
        )
        return response.choices[0].message.content
    except:
        return AI_FALLBACK_PROMPT.format(product_name=product_name)

@app.get("/api/generate", dependencies=[Security(verify_token)])
@limiter.limit("10/minute") # Increased limit for self-hosted
async def generate_menu_item(request: Request, w: str, bgstyle: str = "transparent"):
    
    if not w:
        raise HTTPException(status_code=400, detail="Product name missing")

    try:
        # 1. Determine Style & Prompt
        # 'image': Natural environment
        # 'solid': AI generated studio background (photobooth style)
        # 'transparent' or Hex: Isolated for removal
        
        if bgstyle == "image":
            style_instruction = "Natural, lifestyle, restaurant setting, depth of field."
            needs_rembg = False
        elif bgstyle == "solid":
            style_instruction = "Studio lighting, solid neutral background, soft shadows, minimalist."
            needs_rembg = False
        else:
            # For transparent or specific hex color, we need easy isolation
            style_instruction = "Isolated on white background, top-down view, flat lighting."
            needs_rembg = True

        # 2. DeepSeek (Prompt Generation)
        prompt = get_deepseek_prompt(w, style_instruction)
        print(f"Prompt: {prompt} | Style: {bgstyle}")

        # 3. Replicate (Flux Image Generation)
        output = replicate.run(
            # "black-forest-labs/flux-schnell",
            "google/nano-banana",
            input={"prompt": prompt, "aspect_ratio": "1:1", "output_format": "jpg"}
        )
        image_url = output[0]

        # 4. Download Image
        img_resp = requests.get(image_url)
        input_img = Image.open(io.BytesIO(img_resp.content)).convert("RGBA")

        out = io.BytesIO()

        # 5. Process Image based on bgstyle
        if needs_rembg:
            # Remove Background (Local CPU/GPU)
            no_bg = remove(input_img)
            
            if bgstyle == "transparent":
                # Save as transparent WEBP
                no_bg.save(out, format="WEBP", quality=95)
            else:
                # Assume bgstyle is a Hex Color (e.g., #FF0000)
                try:
                    bg_color_rgb = ImageColor.getrgb(bgstyle)
                    final_bg = Image.new("RGBA", no_bg.size, bg_color_rgb + (255,))
                    composite = Image.alpha_composite(final_bg, no_bg)
                    composite.save(out, format="WEBP", quality=95)
                except ValueError:
                    # Fallback to transparent if hex is invalid
                    print(f"Invalid color code: {bgstyle}, falling back to transparent.")
                    no_bg.save(out, format="WEBP", quality=95)
        else:
            # No background removal needed (image or solid AI style)
            input_img.save(out, format="WEBP", quality=95)

        # 6. Response
        out.seek(0)
        return StreamingResponse(out, media_type="image/webp")

    except Exception as e:
        print(f"Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
