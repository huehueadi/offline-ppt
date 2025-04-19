from flask import Flask, request, jsonify, send_file, redirect, url_for, render_template, session
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.dml.color import RGBColor
import requests
import os
import json
import tempfile
import uuid
import logging
from template_manager import TemplateManager
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3
from io import BytesIO
from flask_cors import CORS
from PIL import Image

app = Flask(__name__)
CORS(app)
template_manager = TemplateManager()

# Configure logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app.secret_key = 'your_secret_key'

def get_db():
    conn = sqlite3.connect('users.db')
    conn.row_factory = sqlite3.Row
    return conn

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        hashed_password = generate_password_hash(password)
        try:
            conn = get_db()
            c = conn.cursor()
            c.execute('INSERT INTO users (username, email, password) VALUES (?, ?, ?)',
                      (username, email, hashed_password))
            conn.commit()
            conn.close()
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            conn.close()
            return render_template('register.html', error='Username or email already exists')
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        conn = get_db()
        c = conn.cursor()
        c.execute('SELECT * FROM users WHERE email = ?', (email,))
        user = c.fetchone()
        conn.close()
        if user and check_password_hash(user['password'], password):
            session['user_id'] = user['id']
            session['username'] = user['username']
            return redirect(url_for('index'))
        else:
            return render_template('login.html', error='Invalid email or password')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    session.pop('username', None)
    return redirect(url_for('login'))

def login_required(f):
    def wrapper(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    wrapper.__name__ = f.__name__
    return wrapper

OLLAMA_ENDPOINT = "http://localhost:11434/api/generate"

def generate_text_content(topic, num_slides):
    try:
        prompt = f"""Generate a detailed JSON for a presentation about '{topic}' with {num_slides} slides.
        Each slide should have the following:
        - A detailed title
        - At least 5 concise and informative bullet points per slide (if applicable)
        - Provide some additional explanations or insights for each bullet point
        - Ensure the content is rich, professional, and informative
        Format EXACTLY as this JSON structure:
        {{
            "title": "Overall Presentation Title",
            "slides": [
                {{
                    "title": "Slide 1 Title",
                    "points": [
                        "Point 1: Detailed explanation or context",
                        "Point 2: Detailed explanation or context",
                        "Point 3: Detailed explanation or context",
                        "Point 4: Additional context or related points",
                        "Point 5: Further insights or examples"
                    ]
                }},
                ...
            ]
        }}
        Requirements:
        - Use clear, professional language
        - Ensure each slide has a meaningful title
        - Create at least 5 detailed, informative bullet points per slide
        - Provide explanations, context, or examples where relevant
        - Avoid any markdown, code blocks, or extra formatting
        """
        payload = {
            "model": "llama3.2:1b",
            "prompt": prompt,
            "stream": False,
            "format": "json"
        }
        response = requests.post(OLLAMA_ENDPOINT, json=payload)
        if response.status_code != 200:
            logger.error(f"Ollama API error: {response.status_code} - {response.text}")
            raise Exception(f"Ollama API error: {response.status_code}")
        content = response.json()["response"]
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            content = content.split("```")[1].split("```")[0].strip()
        presentation_data = json.loads(content)
        if not isinstance(presentation_data, dict) or 'title' not in presentation_data or 'slides' not in presentation_data:
            raise ValueError("Invalid JSON structure")
        for slide in presentation_data.get('slides', []):
            if 'title' not in slide or 'points' not in slide:
                raise ValueError("Invalid slide structure")
        return presentation_data
    except Exception as e:
        logger.error(f"Text generation error: {str(e)}")
        return {
            "title": topic,
            "slides": [
                {
                    "title": f"Introduction to {topic}",
                    "points": [
                        "Overview of the topic with more context and background",
                        "Key points to discuss with additional details",
                        "Importance and relevance with examples or data"
                    ]
                },
                {
                    "title": "Main Concepts",
                    "points": [
                        "First main concept with detailed examples",
                        "Second main concept with further elaboration",
                        "Third main concept with supporting data or case studies"
                    ]
                },
                {
                    "title": "Conclusion",
                    "points": [
                        "Summary of key takeaways with insights",
                        "Future implications with potential applications",
                        "Call to action with a proposed next step or idea"
                    ]
                }
            ]
        }

def generate_image_prompt(prompt):
    return f"Professional presentation image related to: {prompt}"

def create_presentation(content_data, image_prompts=None, template="default"):
    try:
        template_config = template_manager.get_template(template) or template_manager.get_template('default')
        styles = template_config.get('styles', {})
        title_slide_styles = styles.get('title_slide', {})
        content_slide_styles = styles.get('content_slide', {})
        image_slide_styles = styles.get('image_slide', {})
        
        # Log preview image
        preview_image = template_config.get('preview_image', '')
        preview_image_path = os.path.join('static', preview_image)
        if preview_image and os.path.exists(preview_image_path):
            logger.info(f"Preview image found for template {template}: {preview_image_path}")
        else:
            logger.warning(f"Preview image not found for template {template}: {preview_image_path}")
        
        preview_data = {
            "title": content_data.get("title", "Presentation"),
            "template": template,
            "styles": {
                "title_slide": {
                    "background": title_slide_styles.get('background', {'type': 'solid', 'color': {'r': 240, 'g': 240, 'b': 240}}),
                    "background_image": title_slide_styles.get('background_image', ''),
                    "title_font": title_slide_styles.get('title_font', {'name': 'Calibri', 'size': 44, 'color': {'r': 0, 'g': 0, 'b': 0}, 'bold': True, 'alignment': 'center'}),
                    "image_position": title_slide_styles.get('image_position', {'left': 2.5, 'top': 4.0, 'width': 5.0, 'height': 2.5})
                },
                "content_slide": {
                    "background": content_slide_styles.get('background', {'type': 'solid', 'color': {'r': 255, 'g': 255, 'b': 255}}),
                    "background_image": content_slide_styles.get('background_image', ''),
                    "title_font": content_slide_styles.get('title_font', {'name': 'Calibri', 'size': 32, 'color': {'r': 0, 'g': 0, 'b': 0}, 'bold': True, 'alignment': 'left'}),
                    "body_font": content_slide_styles.get('body_font', {'name': 'Calibri', 'size': 18, 'color': {'r': 50, 'g': 50, 'b': 50}, 'alignment': 'left'}),
                    "image_position": content_slide_styles.get('image_position', {'left': 6.0, 'top': 1.5, 'width': 3.5, 'height': 4.5})
                },
                "image_slide": {
                    "fill_color": image_slide_styles.get('fill_color', {'r': 245, 'g': 245, 'b': 245}),
                    "border_color": image_slide_styles.get('border_color', {'r': 200, 'g': 200, 'b': 200}),
                    "border_width": image_slide_styles.get('border_width', 1.5),
                    "border_style": image_slide_styles.get('border_style', 'dashed')
                }
            },
            "slides": []
        }
        
        prs = Presentation()
        SLIDE_WIDTH = Inches(10)  # Standard 4:3 slide width
        SLIDE_HEIGHT = Inches(7.5)  # Standard 4:3 slide height
        SUPPORTED_FORMATS = {'BMP', 'GIF', 'JPEG', 'PNG', 'TIFF', 'WMF'}
        
        def validate_image_format(image_path):
            try:
                with Image.open(image_path) as img:
                    format = img.format.upper()
                    if format not in SUPPORTED_FORMATS:
                        logger.warning(f"Unsupported image format at {image_path}: got {format}, expected one of {SUPPORTED_FORMATS}")
                        return False
                    logger.debug(f"Validated image format at {image_path}: {format}")
                    return True
            except Exception as e:
                logger.error(f"Failed to validate image format at {image_path}: {str(e)}")
                return False
        
        def adjust_font_size(title_text, base_size):
            # Reduce font size for long titles (e.g., > 40 characters)
            if len(title_text) > 40:
                new_size = max(base_size - 8, 20)  # Reduce by up to 8pt, minimum 20pt
                logger.debug(f"Reducing font size for title '{title_text[:20]}...': {base_size}pt to {new_size}pt")
                return new_size
            return base_size
        
        # Title Slide
        blank_slide_layout = prs.slide_layouts[6]
        title_slide = prs.slides.add_slide(blank_slide_layout)
        
        background_settings = title_slide_styles.get('background', {})
        bg_image = title_slide_styles.get('background_image', '')
        background = title_slide.background
        fill = background.fill
        if bg_image:
            bg_image_path = os.path.abspath(os.path.join('static', bg_image))
            logger.debug(f"Checking background image for title slide: {bg_image_path}")
            if os.path.exists(bg_image_path) and validate_image_format(bg_image_path):
                try:
                    logger.info(f"Applying background image for title slide: {bg_image_path}")
                    picture = title_slide.shapes.add_picture(
                        bg_image_path,
                        left=0,
                        top=0,
                        width=SLIDE_WIDTH,
                        height=SLIDE_HEIGHT
                    )
                    logger.debug(f"Picture added to title slide: width={picture.width.inches:.2f}in, height={picture.height.inches:.2f}in, left={picture.left.inches:.2f}in, top={picture.top.inches:.2f}in")
                    title_slide.shapes._spTree.remove(picture._element)
                    title_slide.shapes._spTree.insert(2, picture._element)
                except Exception as e:
                    logger.error(f"Failed to apply background image for title slide: {bg_image_path}, error: {str(e)}")
                    fill.solid()
                    bg_color = background_settings.get('color', {'r': 240, 'g': 240, 'b': 240}) if background_settings.get('type') == 'solid' else background_settings.get('gradient_start', {'r': 240, 'g': 240, 'b': 240})
                    fill.fore_color.rgb = RGBColor(bg_color['r'], bg_color['g'], bg_color['b'])
                    logger.info(f"Fallback to solid color for title slide: rgb({bg_color['r']}, {bg_color['g']}, {bg_color['b']})")
            else:
                logger.error(f"Background image not found or invalid format for title slide: {bg_image_path}")
                fill.solid()
                bg_color = background_settings.get('color', {'r': 240, 'g': 240, 'b': 240}) if background_settings.get('type') == 'solid' else background_settings.get('gradient_start', {'r': 240, 'g': 240, 'b': 240})
                fill.fore_color.rgb = RGBColor(bg_color['r'], bg_color['g'], bg_color['b'])
                logger.info(f"Fallback to solid color for title slide: rgb({bg_color['r']}, {bg_color['g']}, {bg_color['b']})")
        else:
            logger.debug(f"No background image specified for title slide, using {background_settings.get('type', 'solid')} background")
            fill.solid()
            bg_color = background_settings.get('color', {'r': 240, 'g': 240, 'b': 240}) if background_settings.get('type') == 'solid' else background_settings.get('gradient_start', {'r': 240, 'g': 240, 'b': 240})
            fill.fore_color.rgb = RGBColor(bg_color['r'], bg_color['g'], bg_color['b'])
            logger.info(f"Applied solid color for title slide: rgb({bg_color['r']}, {bg_color['g']}, {bg_color['b']})")
        
        # Title slide title textbox
        left = Inches(0.5)
        top = Inches(1.5)
        width = Inches(9.0)
        height = Inches(2.0)  # Increased height to accommodate wrapped text
        title_box = title_slide.shapes.add_textbox(left, top, width, height)
        title_frame = title_box.text_frame
        title_frame.word_wrap = True  # Enable word wrapping
        title_text = content_data.get("title", "Presentation")
        title_frame.text = title_text
        logger.debug(f"Title slide heading: '{title_text}', length: {len(title_text)}")
        title_para = title_frame.paragraphs[0]
        title_font_settings = title_slide_styles.get('title_font', {})
        title_para.font.name = title_font_settings.get('name', 'Calibri')
        base_font_size = title_font_settings.get('size', 44)
        title_para.font.size = Pt(adjust_font_size(title_text, base_font_size))
        title_color = title_font_settings.get('color', {'r': 0, 'g': 0, 'b': 0})
        title_para.font.color.rgb = RGBColor(title_color['r'], title_color['g'], title_color['b'])
        title_para.font.bold = title_font_settings.get('bold', True)
        title_para.alignment = PP_ALIGN.CENTER
        
        title_image_style = {}
        if image_prompts and "title" in image_prompts:
            image_position = title_slide_styles.get('image_position', {'left': 2.5, 'top': 4.0, 'width': 5.0, 'height': 2.5})
            img_left = Inches(image_position.get('left', 2.5))
            img_top = Inches(image_position.get('top', 4.0))
            img_width = Inches(image_position.get('width', 5.0))
            img_height = Inches(image_position.get('height', 2.5))
            img_placeholder = title_slide.shapes.add_shape(1, img_left, img_top, img_width, img_height)
            img_placeholder.fill.solid()
            fill_color = image_slide_styles.get('fill_color', {'r': 245, 'g': 245, 'b': 245})
            img_placeholder.fill.fore_color.rgb = RGBColor(fill_color['r'], fill_color['g'], fill_color['b'])
            border_color = image_slide_styles.get('border_color', {'r': 200, 'g': 200, 'b': 200})
            img_placeholder.line.color.rgb = RGBColor(border_color['r'], border_color['g'], border_color['b'])
            img_placeholder.line.width = Pt(image_slide_styles.get('border_width', 1.5))
            img_placeholder.line.dash_style = 2 if image_slide_styles.get('border_style', 'dashed') == 'dashed' else 1
            text_frame = img_placeholder.text_frame
            text_frame.word_wrap = True
            text_frame.vertical_anchor = MSO_ANCHOR.MIDDLE
            icon_p = text_frame.add_paragraph()
            icon_p.text = "🖼️"
            icon_p.alignment = PP_ALIGN.CENTER
            icon_p.font.size = Pt(48)
            icon_p.space_after = Pt(10)
            prompt_p = text_frame.add_paragraph()
            prompt_p.text = image_prompts['title']
            prompt_p.alignment = PP_ALIGN.CENTER
            prompt_p.font.italic = True
            prompt_p.font.size = Pt(14)
            prompt_p.font.color.rgb = RGBColor(100, 100, 100)
            title_image_style = {
                "left": image_position.get('left', 2.5),
                "top": image_position.get('top', 4.0),
                "width": image_position.get('width', 5.0),
                "height": image_position.get('height', 2.5),
                "fill_color": fill_color,
                "border_color": border_color,
                "border_width": image_slide_styles.get('border_width', 1.5),
                "border_style": image_slide_styles.get('border_style', 'dashed')
            }
        
        preview_data["slides"].append({
            "type": "title",
            "title": content_data.get("title", "Presentation"),
            "has_image": "title" in image_prompts if image_prompts else False,
            "image_prompt": image_prompts.get("title") if image_prompts else None,
            "image_style": title_image_style
        })
        
        # Content Slides
        for i, slide_data in enumerate(content_data.get("slides", [])):
            slide_index = str(i)
            content_slide = prs.slides.add_slide(blank_slide_layout)
            background_settings = content_slide_styles.get('background', {})
            bg_image = content_slide_styles.get('background_image', '')
            background = content_slide.background
            fill = background.fill
            if bg_image:
                bg_image_path = os.path.abspath(os.path.join('static', bg_image))
                logger.debug(f"Checking background image for content slide {i+1}: {bg_image_path}")
                if os.path.exists(bg_image_path) and validate_image_format(bg_image_path):
                    try:
                        logger.info(f"Applying background image for content slide {i+1}: {bg_image_path}")
                        picture = content_slide.shapes.add_picture(
                            bg_image_path,
                            left=0,
                            top=0,
                            width=SLIDE_WIDTH,
                            height=SLIDE_HEIGHT
                        )
                        logger.debug(f"Picture added to content slide {i+1}: width={picture.width.inches:.2f}in, height={picture.height.inches:.2f}in, left={picture.left.inches:.2f}in, top={picture.top.inches:.2f}in")
                        content_slide.shapes._spTree.remove(picture._element)
                        content_slide.shapes._spTree.insert(2, picture._element)
                    except Exception as e:
                        logger.error(f"Failed to apply background image for content slide {i+1}: {bg_image_path}, error: {str(e)}")
                        fill.solid()
                        bg_color = background_settings.get('color', {'r': 255, 'g': 255, 'b': 255}) if background_settings.get('type') == 'solid' else background_settings.get('gradient_start', {'r': 255, 'g': 255, 'b': 255})
                        fill.fore_color.rgb = RGBColor(bg_color['r'], bg_color['g'], bg_color['b'])
                        logger.info(f"Fallback to solid color for content slide {i+1}: rgb({bg_color['r']}, {bg_color['g']}, {bg_color['b']})")
                else:
                    logger.error(f"Background image not found or invalid format for content slide {i+1}: {bg_image_path}")
                    fill.solid()
                    bg_color = background_settings.get('color', {'r': 255, 'g': 255, 'b': 255}) if background_settings.get('type') == 'solid' else background_settings.get('gradient_start', {'r': 255, 'g': 255, 'b': 255})
                    fill.fore_color.rgb = RGBColor(bg_color['r'], bg_color['g'], bg_color['b'])
                    logger.info(f"Fallback to solid color for content slide {i+1}: rgb({bg_color['r']}, {bg_color['g']}, {bg_color['b']})")
            else:
                logger.debug(f"No background image specified for content slide {i+1}, using {background_settings.get('type', 'solid')} background")
                fill.solid()
                bg_color = background_settings.get('color', {'r': 255, 'g': 255, 'b': 255}) if background_settings.get('type') == 'solid' else background_settings.get('gradient_start', {'r': 255, 'g': 255, 'b': 255})
                fill.fore_color.rgb = RGBColor(bg_color['r'], bg_color['g'], bg_color['b'])
                logger.info(f"Applied solid color for content slide {i+1}: rgb({bg_color['r']}, {bg_color['g']}, {bg_color['b']})")
            
            # Content slide title textbox
            title_left = Inches(0.5)
            title_top = Inches(0.5)
            title_width = Inches(9.0)
            title_height = Inches(1.2)  # Increased height for wrapped text
            title_box = content_slide.shapes.add_textbox(title_left, title_top, title_width, title_height)
            title_frame = title_box.text_frame
            title_frame.word_wrap = True  # Enable word wrapping
            title_text = slide_data.get("title", f"Slide {i+1}")
            title_frame.text = title_text
            logger.debug(f"Content slide {i+1} heading: '{title_text}', length: {len(title_text)}")
            title_para = title_frame.paragraphs[0]
            title_font = content_slide_styles.get('title_font', {})
            title_para.font.name = title_font.get('name', 'Calibri')
            base_font_size = title_font.get('size', 32)
            title_para.font.size = Pt(adjust_font_size(title_text, base_font_size))
            title_color = title_font.get('color', {'r': 0, 'g': 0, 'b': 0})
            title_para.font.color.rgb = RGBColor(title_color['r'], title_color['g'], title_color['b'])
            title_para.font.bold = title_font.get('bold', True)
            title_para.alignment = {
                'center': PP_ALIGN.CENTER,
                'left': PP_ALIGN.LEFT,
                'right': PP_ALIGN.RIGHT
            }.get(title_font.get('alignment', 'left'), PP_ALIGN.LEFT)
            
            points_styling = []
            if slide_data.get("points", []):
                content_left = Inches(0.5)
                content_top = Inches(2.0)  # Adjusted to account for taller title
                content_width = Inches(5.0)
                content_height = Inches(4.0)  # Reduced to fit taller title
                content_box = content_slide.shapes.add_textbox(content_left, content_top, content_width, content_height)
                text_frame = content_box.text_frame
                text_frame.word_wrap = True
                body_font = content_slide_styles.get('body_font', {})
                for point in slide_data.get("points", []):
                    if text_frame.paragraphs and text_frame.paragraphs[0].text == "":
                        p = text_frame.paragraphs[0]
                    else:
                        p = text_frame.add_paragraph()
                    p.text = "• " + point
                    p.font.name = body_font.get('name', 'Calibri')
                    p.font.size = Pt(body_font.get('size', 18))
                    body_color = body_font.get('color', {'r': 50, 'g': 50, 'b': 50})
                    p.font.color.rgb = RGBColor(body_color['r'], body_color['g'], body_color['b'])
                    p.space_before = Pt(6)
                    p.space_after = Pt(6)
                    p.alignment = {
                        'center': PP_ALIGN.CENTER,
                        'left': PP_ALIGN.LEFT,
                        'right': PP_ALIGN.RIGHT
                    }.get(body_font.get('alignment', 'left'), PP_ALIGN.LEFT)
                    points_styling.append({
                        "text": point,
                        "level": 0,
                        "font_name": body_font.get('name', 'Calibri'),
                        "font_size": body_font.get('size', 18),
                        "color": body_color,
                        "alignment": body_font.get('alignment', 'left'),
                        "space_before": 6,
                        "space_after": 6
                    })
            
            content_image_style = {}
            if image_prompts and slide_index in image_prompts:
                image_position = content_slide_styles.get('image_position', {'left': 6.0, 'top': 2.0, 'width': 3.5, 'height': 4.0})
                img_left = Inches(image_position.get('left', 6.0))
                img_top = Inches(image_position.get('top', 2.0))
                img_width = Inches(image_position.get('width', 3.5))
                img_height = Inches(image_position.get('height', 4.0))
                img_placeholder = content_slide.shapes.add_shape(1, img_left, img_top, img_width, img_height)
                img_placeholder.fill.solid()
                fill_color = image_slide_styles.get('fill_color', {'r': 245, 'g': 245, 'b': 245})
                img_placeholder.fill.fore_color.rgb = RGBColor(fill_color['r'], fill_color['g'], fill_color['b'])
                border_color = image_slide_styles.get('border_color', {'r': 200, 'g': 200, 'b': 200})
                img_placeholder.line.color.rgb = RGBColor(border_color['r'], border_color['g'], border_color['b'])
                img_placeholder.line.width = Pt(image_slide_styles.get('border_width', 1.5))
                img_placeholder.line.dash_style = 2 if image_slide_styles.get('border_style', 'dashed') == 'dashed' else 1
                text_frame = img_placeholder.text_frame
                text_frame.word_wrap = True
                text_frame.vertical_anchor = MSO_ANCHOR.MIDDLE
                icon_p = text_frame.add_paragraph()
                icon_p.text = "🖼️"
                icon_p.alignment = PP_ALIGN.CENTER
                icon_p.font.size = Pt(48)
                icon_p.space_after = Pt(10)
                prompt_p = text_frame.add_paragraph()
                prompt_p.text = image_prompts[slide_index]
                prompt_p.alignment = PP_ALIGN.CENTER
                prompt_p.font.italic = True
                prompt_p.font.size = Pt(14)
                prompt_p.font.color.rgb = RGBColor(100, 100, 100)
                content_image_style = {
                    "left": image_position.get('left', 6.0),
                    "top": image_position.get('top', 2.0),
                    "width": image_position.get('width', 3.5),
                    "height": image_position.get('height', 4.0),
                    "fill_color": fill_color,
                    "border_color": border_color,
                    "border_width": image_slide_styles.get('border_width', 1.5),
                    "border_style": image_slide_styles.get('border_style', 'dashed')
                }
            
            preview_data["slides"].append({
                "type": "content",
                "title": slide_data.get("title", f"Slide {i+1}"),
                "points": slide_data.get("points", []),
                "points_styling": points_styling,
                "has_image": slide_index in image_prompts if image_prompts else False,
                "image_prompt": image_prompts.get(slide_index) if image_prompts else None,
                "image_style": content_image_style
            })
        
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".pptx")
        prs.save(temp_file.name)
        temp_file.close()
        return temp_file.name, preview_data
    
    except Exception as e:
        logger.error(f"PowerPoint creation error: {str(e)}")
        raise Exception(f"Failed to create PowerPoint: {str(e)}")

@app.route('/generate_ppt', methods=['POST'])
def generate_ppt():
    try:
        data = request.json
        topic = data.get('topic')
        num_slides = int(data.get('num_slides', 3))
        template = data.get('template', 'default')
        if not topic:
            return jsonify({"error": "Topic is required"}), 400
        if num_slides < 1 or num_slides > 20:
            return jsonify({"error": "Number of slides must be between 1 and 20"}), 400
        logger.info(f"Generating content for topic: {topic} with {num_slides} slides using template: {template}")
        content_data = generate_text_content(topic, num_slides)
        image_prompts = {}
        try:
            logger.info("Generating title image prompt")
            title_image_prompt = generate_image_prompt(topic)
            if title_image_prompt:
                image_prompts["title"] = title_image_prompt
            logger.info("Generating slide image prompts")
            for i, slide_data in enumerate(content_data.get("slides", [])):
                slide_title = slide_data.get("title", "")
                slide_image_prompt = generate_image_prompt(f"{topic} - {slide_title}")
                if slide_image_prompt:
                    image_prompts[str(i)] = slide_image_prompt
        except Exception as e:
            logger.warning(f"Image prompt generation failed: {str(e)}")
        logger.info(f"Creating PowerPoint presentation with template: {template}")
        ppt_file, preview_data = create_presentation(content_data, image_prompts, template)
        unique_id = uuid.uuid4().hex[:8]
        filename = f"{topic.replace(' ', '_')}_{unique_id}.pptx"
        user_filename = os.path.join("static", "downloads", filename)
        os.makedirs(os.path.dirname(user_filename), exist_ok=True)
        with open(ppt_file, 'rb') as src, open(user_filename, 'wb') as dst:
            dst.write(src.read())
        os.unlink(ppt_file)
        return jsonify({
            "success": True,
            "filename": filename,
            "download_url": f"/static/downloads/{filename}",
            "content": content_data,
            "image_prompts": image_prompts,
            "template": template,
            "preview_data": preview_data
        })
    except Exception as e:
        logger.error(f"Error processing request: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/update_ppt', methods=['POST'])
def update_ppt():
    try:
        data = request.json
        content_data = data.get('content')
        image_prompts = data.get('image_prompts', {})
        template = data.get('template', 'default')
        if not content_data or 'title' not in content_data or 'slides' not in content_data:
            return jsonify({"error": "Invalid presentation content"}), 400
        logger.info("Creating updated PowerPoint presentation")
        ppt_file, preview_data = create_presentation(content_data, image_prompts, template)
        unique_id = uuid.uuid4().hex[:8]
        topic = content_data.get("title", "Presentation").replace(' ', '_')
        filename = f"{topic}_{unique_id}.pptx"
        user_filename = os.path.join("static", "downloads", filename)
        os.makedirs(os.path.dirname(user_filename), exist_ok=True)
        with open(ppt_file, 'rb') as src, open(user_filename, 'wb') as dst:
            dst.write(src.read())
        os.unlink(ppt_file)
        return jsonify({
            "success": True,
            "filename": filename,
            "download_url": f"/static/downloads/{filename}",
            "preview_data": preview_data
        })
    except Exception as e:
        logger.error(f"Error updating presentation: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/')
def index():
    return app.send_static_file('index.html')

@app.route('/static/<path:path>')
def serve_static(path):
    logger.debug(f"Serving static file: {path}")
    return app.send_static_file(path)

@app.route('/get_templates', methods=['GET'])
def get_templates():
    try:
        templates = template_manager.get_all_templates()
        template_response = {}
        for key, template in templates.items():
            template_response[key] = {
                "name": template.get('name', key),
                "description": template.get('description', ''),
                "preview_image": template.get('preview_image', ''),
                "styles": template.get('styles', {})
            }
        logger.info(f"Returning {len(template_response)} templates")
        return jsonify({
            "success": True,
            "templates": template_response
        })
    except Exception as e:
        logger.error(f"Error retrieving templates: {str(e)}")
        return jsonify({"error": "Failed to retrieve templates"}), 500

@app.route('/download/<filename>')
def download_file(filename):
    file_path = os.path.join("static", "downloads", filename)
    if not os.path.exists(file_path):
        logger.error(f"Download file not found: {file_path}")
        return jsonify({"error": "File not found"}), 404
    logger.info(f"Downloading file: {file_path}")
    return send_file(file_path, as_attachment=True)

if __name__ == '__main__':
    os.makedirs(os.path.join("static", "downloads"), exist_ok=True)
    app.run(debug=True)


# from flask import Flask, request, jsonify, send_file, redirect, url_for, render_template, session
# from pptx import Presentation
# from pptx.util import Inches, Pt
# from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
# from pptx.dml.color import RGBColor
# import requests
# import os
# import json
# import tempfile
# import uuid
# import logging
# from template_manager import TemplateManager
# from werkzeug.security import generate_password_hash, check_password_hash
# import sqlite3
# from io import BytesIO
# from flask_cors import CORS

# app = Flask(__name__)
# CORS(app)
# template_manager = TemplateManager()

# # Configure logging
# logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
# logger = logging.getLogger(__name__)

# app.secret_key = 'your_secret_key'

# def get_db():
#     conn = sqlite3.connect('users.db')
#     conn.row_factory = sqlite3.Row
#     return conn

# @app.route('/register', methods=['GET', 'POST'])
# def register():
#     if request.method == 'POST':
#         username = request.form['username']
#         email = request.form['email']
#         password = request.form['password']
#         hashed_password = generate_password_hash(password)
#         try:
#             conn = get_db()
#             c = conn.cursor()
#             c.execute('INSERT INTO users (username, email, password) VALUES (?, ?, ?)',
#                       (username, email, hashed_password))
#             conn.commit()
#             conn.close()
#             return redirect(url_for('login'))
#         except sqlite3.IntegrityError:
#             conn.close()
#             return render_template('register.html', error='Username or email already exists')
#     return render_template('register.html')

# @app.route('/login', methods=['GET', 'POST'])
# def login():
#     if request.method == 'POST':
#         email = request.form['email']
#         password = request.form['password']
#         conn = get_db()
#         c = conn.cursor()
#         c.execute('SELECT * FROM users WHERE email = ?', (email,))
#         user = c.fetchone()
#         conn.close()
#         if user and check_password_hash(user['password'], password):
#             session['user_id'] = user['id']
#             session['username'] = user['username']
#             return redirect(url_for('index'))
#         else:
#             return render_template('login.html', error='Invalid email or password')
#     return render_template('login.html')

# @app.route('/logout')
# def logout():
#     session.pop('user_id', None)
#     session.pop('username', None)
#     return redirect(url_for('login'))

# def login_required(f):
#     def wrapper(*args, **kwargs):
#         if 'user_id' not in session:
#             return redirect(url_for('login'))
#         return f(*args, **kwargs)
#     wrapper.__name__ = f.__name__
#     return wrapper

# OLLAMA_ENDPOINT = "http://localhost:11434/api/generate"

# def generate_text_content(topic, num_slides):
#     try:
#         prompt = f"""Generate a detailed JSON for a presentation about '{topic}' with {num_slides} slides.
#         Each slide should have the following:
#         - A detailed title
#         - At least 5 concise and informative bullet points per slide (if applicable)
#         - Provide some additional explanations or insights for each bullet point
#         - Ensure the content is rich, professional, and informative
#         Format EXACTLY as this JSON structure:
#         {{
#             "title": "Overall Presentation Title",
#             "slides": [
#                 {{
#                     "title": "Slide 1 Title",
#                     "points": [
#                         "Point 1: Detailed explanation or context",
#                         "Point 2: Detailed explanation or context",
#                         "Point 3: Detailed explanation or context",
#                         "Point 4: Additional context or related points",
#                         "Point 5: Further insights or examples"
#                     ]
#                 }},
#                 ...
#             ]
#         }}
#         Requirements:
#         - Use clear, professional language
#         - Ensure each slide has a meaningful title
#         - Create at least 5 detailed, informative bullet points per slide
#         - Provide explanations, context, or examples where relevant
#         - Avoid any markdown, code blocks, or extra formatting
#         """
#         payload = {
#             "model": "llama3.2:1b",
#             "prompt": prompt,
#             "stream": False,
#             "format": "json"
#         }
#         response = requests.post(OLLAMA_ENDPOINT, json=payload)
#         if response.status_code != 200:
#             logger.error(f"Ollama API error: {response.status_code} - {response.text}")
#             raise Exception(f"Ollama API error: {response.status_code}")
#         content = response.json()["response"]
#         if "```json" in content:
#             content = content.split("```json")[1].split("```")[0].strip()
#         elif "```" in content:
#             content = content.split("```")[1].split("```")[0].strip()
#         presentation_data = json.loads(content)
#         if not isinstance(presentation_data, dict) or 'title' not in presentation_data or 'slides' not in presentation_data:
#             raise ValueError("Invalid JSON structure")
#         for slide in presentation_data.get('slides', []):
#             if 'title' not in slide or 'points' not in slide:
#                 raise ValueError("Invalid slide structure")
#         return presentation_data
#     except Exception as e:
#         logger.error(f"Text generation error: {str(e)}")
#         return {
#             "title": topic,
#             "slides": [
#                 {
#                     "title": f"Introduction to {topic}",
#                     "points": [
#                         "Overview of the topic with more context and background",
#                         "Key points to discuss with additional details",
#                         "Importance and relevance with examples or data"
#                     ]
#                 },
#                 {
#                     "title": "Main Concepts",
#                     "points": [
#                         "First main concept with detailed examples",
#                         "Second main concept with further elaboration",
#                         "Third main concept with supporting data or case studies"
#                     ]
#                 },
#                 {
#                     "title": "Conclusion",
#                     "points": [
#                         "Summary of key takeaways with insights",
#                         "Future implications with potential applications",
#                         "Call to action with a proposed next step or idea"
#                     ]
#                 }
#             ]
#         }

# def generate_image_prompt(prompt):
#     return f"Professional presentation image related to: {prompt}"

# def create_presentation(content_data, image_prompts=None, template="default"):
#     try:
#         template_config = template_manager.get_template(template) or template_manager.get_template('default')
#         styles = template_config.get('styles', {})
#         title_slide_styles = styles.get('title_slide', {})
#         content_slide_styles = styles.get('content_slide', {})
#         image_slide_styles = styles.get('image_slide', {})
        
#         # Log preview image
#         preview_image = template_config.get('preview_image', '')
#         preview_image_path = os.path.join('static', preview_image)
#         if preview_image and os.path.exists(preview_image_path):
#             logger.info(f"Preview image found for template {template}: {preview_image_path}")
#         else:
#             logger.warning(f"Preview image not found for template {template}: {preview_image_path}")
        
#         preview_data = {
#             "title": content_data.get("title", "Presentation"),
#             "template": template,
#             "styles": {
#                 "title_slide": {
#                     "background": title_slide_styles.get('background', {'type': 'solid', 'color': {'r': 240, 'g': 240, 'b': 240}}),
#                     "background_image": title_slide_styles.get('background_image', ''),
#                     "title_font": title_slide_styles.get('title_font', {'name': 'Calibri', 'size': 44, 'color': {'r': 0, 'g': 0, 'b': 0}, 'bold': True, 'alignment': 'center'}),
#                     "image_position": title_slide_styles.get('image_position', {'left': 2.5, 'top': 4.0, 'width': 5.0, 'height': 2.5})
#                 },
#                 "content_slide": {
#                     "background": content_slide_styles.get('background', {'type': 'solid', 'color': {'r': 255, 'g': 255, 'b': 255}}),
#                     "background_image": content_slide_styles.get('background_image', ''),
#                     "title_font": content_slide_styles.get('title_font', {'name': 'Calibri', 'size': 32, 'color': {'r': 0, 'g': 0, 'b': 0}, 'bold': True, 'alignment': 'left'}),
#                     "body_font": content_slide_styles.get('body_font', {'name': 'Calibri', 'size': 18, 'color': {'r': 50, 'g': 50, 'b': 50}, 'alignment': 'left'}),
#                     "image_position": content_slide_styles.get('image_position', {'left': 6.0, 'top': 1.5, 'width': 3.5, 'height': 4.5})
#                 },
#                 "image_slide": {
#                     "fill_color": image_slide_styles.get('fill_color', {'r': 245, 'g': 245, 'b': 245}),
#                     "border_color": image_slide_styles.get('border_color', {'r': 200, 'g': 200, 'b': 200}),
#                     "border_width": image_slide_styles.get('border_width', 1.5),
#                     "border_style": image_slide_styles.get('border_style', 'dashed')
#                 }
#             },
#             "slides": []
#         }
        
#         prs = Presentation()
#         SLIDE_WIDTH = Inches(10)  # Standard 4:3 slide width
#         SLIDE_HEIGHT = Inches(7.5)  # Standard 4:3 slide height
        
#         # Title Slide
#         blank_slide_layout = prs.slide_layouts[6]
#         title_slide = prs.slides.add_slide(blank_slide_layout)
        
#         background_settings = title_slide_styles.get('background', {})
#         bg_image = title_slide_styles.get('background_image', '')
#         background = title_slide.background
#         fill = background.fill
#         if bg_image:
#             # Use absolute path for image
#             bg_image_path = os.path.abspath(os.path.join('static', bg_image))
#             logger.debug(f"Checking background image for title slide: {bg_image_path}")
#             if os.path.exists(bg_image_path):
#                 try:
#                     logger.info(f"Applying background image for title slide: {bg_image_path}")
#                     # Add picture as a shape to cover the entire slide
#                     picture = title_slide.shapes.add_picture(
#                         bg_image_path,
#                         left=0,
#                         top=0,
#                         width=SLIDE_WIDTH,
#                         height=SLIDE_HEIGHT
#                     )
#                     # Log picture properties
#                     logger.debug(f"Picture added to title slide: width={picture.width.inches:.2f}in, height={picture.height.inches:.2f}in, left={picture.left.inches:.2f}in, top={picture.top.inches:.2f}in")
#                     # Send picture to back to ensure text is visible
#                     title_slide.shapes._spTree.remove(picture._element)
#                     title_slide.shapes._spTree.insert(2, picture._element)  # Insert at the back
#                 except Exception as e:
#                     logger.error(f"Failed to apply background image for title slide: {bg_image_path}, error: {str(e)}")
#                     fill.solid()
#                     bg_color = background_settings.get('color', {'r': 240, 'g': 240, 'b': 240}) if background_settings.get('type') == 'solid' else background_settings.get('gradient_start', {'r': 240, 'g': 240, 'b': 240})
#                     fill.fore_color.rgb = RGBColor(bg_color['r'], bg_color['g'], bg_color['b'])
#                     logger.info(f"Fallback to solid color for title slide: rgb({bg_color['r']}, {bg_color['g']}, {bg_color['b']})")
#             else:
#                 logger.error(f"Background image not found for title slide: {bg_image_path}")
#                 fill.solid()
#                 bg_color = background_settings.get('color', {'r': 240, 'g': 240, 'b': 240}) if background_settings.get('type') == 'solid' else background_settings.get('gradient_start', {'r': 240, 'g': 240, 'b': 240})
#                 fill.fore_color.rgb = RGBColor(bg_color['r'], bg_color['g'], bg_color['b'])
#                 logger.info(f"Fallback to solid color for title slide: rgb({bg_color['r']}, {bg_color['g']}, {bg_color['b']})")
#         else:
#             logger.debug(f"No background image specified for title slide, using {background_settings.get('type', 'solid')} background")
#             fill.solid()
#             bg_color = background_settings.get('color', {'r': 240, 'g': 240, 'b': 240}) if background_settings.get('type') == 'solid' else background_settings.get('gradient_start', {'r': 240, 'g': 240, 'b': 240})
#             fill.fore_color.rgb = RGBColor(bg_color['r'], bg_color['g'], bg_color['b'])
#             logger.info(f"Applied solid color for title slide: rgb({bg_color['r']}, {bg_color['g']}, {bg_color['b']})")
        
#         left = Inches(1.0)
#         top = Inches(2.0)
#         width = Inches(8.0)
#         height = Inches(1.5)
#         title_box = title_slide.shapes.add_textbox(left, top, width, height)
#         title_frame = title_box.text_frame
#         title_frame.text = content_data.get("title", "Presentation")
#         title_para = title_frame.paragraphs[0]
#         title_font_settings = title_slide_styles.get('title_font', {})
#         title_para.font.name = title_font_settings.get('name', 'Calibri')
#         title_para.font.size = Pt(title_font_settings.get('size', 44))
#         title_color = title_font_settings.get('color', {'r': 0, 'g': 0, 'b': 0})
#         title_para.font.color.rgb = RGBColor(title_color['r'], title_color['g'], title_color['b'])
#         title_para.font.bold = title_font_settings.get('bold', True)
#         title_para.alignment = PP_ALIGN.CENTER
        
#         title_image_style = {}
#         if image_prompts and "title" in image_prompts:
#             image_position = title_slide_styles.get('image_position', {'left': 2.5, 'top': 4.0, 'width': 5.0, 'height': 2.5})
#             img_left = Inches(image_position.get('left', 2.5))
#             img_top = Inches(image_position.get('top', 4.0))
#             img_width = Inches(image_position.get('width', 5.0))
#             img_height = Inches(image_position.get('height', 2.5))
#             img_placeholder = title_slide.shapes.add_shape(1, img_left, img_top, img_width, img_height)
#             img_placeholder.fill.solid()
#             fill_color = image_slide_styles.get('fill_color', {'r': 245, 'g': 245, 'b': 245})
#             img_placeholder.fill.fore_color.rgb = RGBColor(fill_color['r'], fill_color['g'], fill_color['b'])
#             border_color = image_slide_styles.get('border_color', {'r': 200, 'g': 200, 'b': 200})
#             img_placeholder.line.color.rgb = RGBColor(border_color['r'], border_color['g'], border_color['b'])
#             img_placeholder.line.width = Pt(image_slide_styles.get('border_width', 1.5))
#             img_placeholder.line.dash_style = 2 if image_slide_styles.get('border_style', 'dashed') == 'dashed' else 1
#             text_frame = img_placeholder.text_frame
#             text_frame.word_wrap = True
#             text_frame.vertical_anchor = MSO_ANCHOR.MIDDLE
#             icon_p = text_frame.add_paragraph()
#             icon_p.text = "🖼️"
#             icon_p.alignment = PP_ALIGN.CENTER
#             icon_p.font.size = Pt(48)
#             icon_p.space_after = Pt(10)
#             prompt_p = text_frame.add_paragraph()
#             prompt_p.text = image_prompts['title']
#             prompt_p.alignment = PP_ALIGN.CENTER
#             prompt_p.font.italic = True
#             prompt_p.font.size = Pt(14)
#             prompt_p.font.color.rgb = RGBColor(100, 100, 100)
#             title_image_style = {
#                 "left": image_position.get('left', 2.5),
#                 "top": image_position.get('top', 4.0),
#                 "width": image_position.get('width', 5.0),
#                 "height": image_position.get('height', 2.5),
#                 "fill_color": fill_color,
#                 "border_color": border_color,
#                 "border_width": image_slide_styles.get('border_width', 1.5),
#                 "border_style": image_slide_styles.get('border_style', 'dashed')
#             }
        
#         preview_data["slides"].append({
#             "type": "title",
#             "title": content_data.get("title", "Presentation"),
#             "has_image": "title" in image_prompts if image_prompts else False,
#             "image_prompt": image_prompts.get("title") if image_prompts else None,
#             "image_style": title_image_style
#         })
        
#         # Content Slides
#         for i, slide_data in enumerate(content_data.get("slides", [])):
#             slide_index = str(i)
#             content_slide = prs.slides.add_slide(blank_slide_layout)
#             background_settings = content_slide_styles.get('background', {})
#             bg_image = content_slide_styles.get('background_image', '')
#             background = content_slide.background
#             fill = background.fill
#             if bg_image:
#                 # Use absolute path for image
#                 bg_image_path = os.path.abspath(os.path.join('static', bg_image))
#                 logger.debug(f"Checking background image for content slide {i+1}: {bg_image_path}")
#                 if os.path.exists(bg_image_path):
#                     try:
#                         logger.info(f"Applying background image for content slide {i+1}: {bg_image_path}")
#                         # Add picture as a shape to cover the entire slide
#                         picture = content_slide.shapes.add_picture(
#                             bg_image_path,
#                             left=0,
#                             top=0,
#                             width=SLIDE_WIDTH,
#                             height=SLIDE_HEIGHT
#                         )
#                         # Log picture properties
#                         logger.debug(f"Picture added to content slide {i+1}: width={picture.width.inches:.2f}in, height={picture.height.inches:.2f}in, left={picture.left.inches:.2f}in, top={picture.top.inches:.2f}in")
#                         # Send picture to back to ensure text is visible
#                         content_slide.shapes._spTree.remove(picture._element)
#                         content_slide.shapes._spTree.insert(2, picture._element)  # Insert at the back
#                     except Exception as e:
#                         logger.error(f"Failed to apply background image for content slide {i+1}: {bg_image_path}, error: {str(e)}")
#                         fill.solid()
#                         bg_color = background_settings.get('color', {'r': 255, 'g': 255, 'b': 255}) if background_settings.get('type') == 'solid' else background_settings.get('gradient_start', {'r': 255, 'g': 255, 'b': 255})
#                         fill.fore_color.rgb = RGBColor(bg_color['r'], bg_color['g'], bg_color['b'])
#                         logger.info(f"Fallback to solid color for content slide {i+1}: rgb({bg_color['r']}, {bg_color['g']}, {bg_color['b']})")
#                 else:
#                     logger.error(f"Background image not found for content slide {i+1}: {bg_image_path}")
#                     fill.solid()
#                     bg_color = background_settings.get('color', {'r': 255, 'g': 255, 'b': 255}) if background_settings.get('type') == 'solid' else background_settings.get('gradient_start', {'r': 255, 'g': 255, 'b': 255})
#                     fill.fore_color.rgb = RGBColor(bg_color['r'], bg_color['g'], bg_color['b'])
#                     logger.info(f"Fallback to solid color for content slide {i+1}: rgb({bg_color['r']}, {bg_color['g']}, {bg_color['b']})")
#             else:
#                 logger.debug(f"No background image specified for content slide {i+1}, using {background_settings.get('type', 'solid')} background")
#                 fill.solid()
#                 bg_color = background_settings.get('color', {'r': 255, 'g': 255, 'b': 255}) if background_settings.get('type') == 'solid' else background_settings.get('gradient_start', {'r': 255, 'g': 255, 'b': 255})
#                 fill.fore_color.rgb = RGBColor(bg_color['r'], bg_color['g'], bg_color['b'])
#                 logger.info(f"Applied solid color for content slide {i+1}: rgb({bg_color['r']}, {bg_color['g']}, {bg_color['b']})")
            
#             title_left = Inches(0.5)
#             title_top = Inches(0.5)
#             title_width = Inches(9.0)
#             title_height = Inches(0.8)
#             title_box = content_slide.shapes.add_textbox(title_left, title_top, title_width, title_height)
#             title_frame = title_box.text_frame
#             title_frame.text = slide_data.get("title", f"Slide {i+1}")
#             title_para = title_frame.paragraphs[0]
#             title_font = content_slide_styles.get('title_font', {})
#             title_para.font.name = title_font.get('name', 'Calibri')
#             title_para.font.size = Pt(title_font.get('size', 32))
#             title_color = title_font.get('color', {'r': 0, 'g': 0, 'b': 0})
#             title_para.font.color.rgb = RGBColor(title_color['r'], title_color['g'], title_color['b'])
#             title_para.font.bold = title_font.get('bold', True)
#             title_para.alignment = {
#                 'center': PP_ALIGN.CENTER,
#                 'left': PP_ALIGN.LEFT,
#                 'right': PP_ALIGN.RIGHT
#             }.get(title_font.get('alignment', 'left'), PP_ALIGN.LEFT)
            
#             points_styling = []
#             if slide_data.get("points", []):
#                 content_left = Inches(0.5)
#                 content_top = Inches(1.5)
#                 content_width = Inches(5.0)
#                 content_height = Inches(4.5)
#                 content_box = content_slide.shapes.add_textbox(content_left, content_top, content_width, content_height)
#                 text_frame = content_box.text_frame
#                 text_frame.word_wrap = True
#                 body_font = content_slide_styles.get('body_font', {})
#                 for point in slide_data.get("points", []):
#                     if text_frame.paragraphs and text_frame.paragraphs[0].text == "":
#                         p = text_frame.paragraphs[0]
#                     else:
#                         p = text_frame.add_paragraph()
#                     p.text = "• " + point
#                     p.font.name = body_font.get('name', 'Calibri')
#                     p.font.size = Pt(body_font.get('size', 18))
#                     body_color = body_font.get('color', {'r': 50, 'g': 50, 'b': 50})
#                     p.font.color.rgb = RGBColor(body_color['r'], body_color['g'], body_color['b'])
#                     p.space_before = Pt(6)
#                     p.space_after = Pt(6)
#                     p.alignment = {
#                         'center': PP_ALIGN.CENTER,
#                         'left': PP_ALIGN.LEFT,
#                         'right': PP_ALIGN.RIGHT
#                     }.get(body_font.get('alignment', 'left'), PP_ALIGN.LEFT)
#                     points_styling.append({
#                         "text": point,
#                         "level": 0,
#                         "font_name": body_font.get('name', 'Calibri'),
#                         "font_size": body_font.get('size', 18),
#                         "color": body_color,
#                         "alignment": body_font.get('alignment', 'left'),
#                         "space_before": 6,
#                         "space_after": 6
#                     })
            
#             content_image_style = {}
#             if image_prompts and slide_index in image_prompts:
#                 image_position = content_slide_styles.get('image_position', {'left': 6.0, 'top': 1.5, 'width': 3.5, 'height': 4.5})
#                 img_left = Inches(image_position.get('left', 6.0))
#                 img_top = Inches(image_position.get('top', 1.5))
#                 img_width = Inches(image_position.get('width', 3.5))
#                 img_height = Inches(image_position.get('height', 4.5))
#                 img_placeholder = content_slide.shapes.add_shape(1, img_left, img_top, img_width, img_height)
#                 img_placeholder.fill.solid()
#                 fill_color = image_slide_styles.get('fill_color', {'r': 245, 'g': 245, 'b': 245})
#                 img_placeholder.fill.fore_color.rgb = RGBColor(fill_color['r'], fill_color['g'], fill_color['b'])
#                 border_color = image_slide_styles.get('border_color', {'r': 200, 'g': 200, 'b': 200})
#                 img_placeholder.line.color.rgb = RGBColor(border_color['r'], border_color['g'], border_color['b'])
#                 img_placeholder.line.width = Pt(image_slide_styles.get('border_width', 1.5))
#                 img_placeholder.line.dash_style = 2 if image_slide_styles.get('border_style', 'dashed') == 'dashed' else 1
#                 text_frame = img_placeholder.text_frame
#                 text_frame.word_wrap = True
#                 text_frame.vertical_anchor = MSO_ANCHOR.MIDDLE
#                 icon_p = text_frame.add_paragraph()
#                 icon_p.text = "🖼️"
#                 icon_p.alignment = PP_ALIGN.CENTER
#                 icon_p.font.size = Pt(48)
#                 icon_p.space_after = Pt(10)
#                 prompt_p = text_frame.add_paragraph()
#                 prompt_p.text = image_prompts[slide_index]
#                 prompt_p.alignment = PP_ALIGN.CENTER
#                 prompt_p.font.italic = True
#                 prompt_p.font.size = Pt(14)
#                 prompt_p.font.color.rgb = RGBColor(100, 100, 100)
#                 content_image_style = {
#                     "left": image_position.get('left', 6.0),
#                     "top": image_position.get('top', 1.5),
#                     "width": image_position.get('width', 3.5),
#                     "height": image_position.get('height', 4.5),
#                     "fill_color": fill_color,
#                     "border_color": border_color,
#                     "border_width": image_slide_styles.get('border_width', 1.5),
#                     "border_style": image_slide_styles.get('border_style', 'dashed')
#                 }
            
#             preview_data["slides"].append({
#                 "type": "content",
#                 "title": slide_data.get("title", f"Slide {i+1}"),
#                 "points": slide_data.get("points", []),
#                 "points_styling": points_styling,
#                 "has_image": slide_index in image_prompts if image_prompts else False,
#                 "image_prompt": image_prompts.get(slide_index) if image_prompts else None,
#                 "image_style": content_image_style
#             })
        
#         temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".pptx")
#         prs.save(temp_file.name)
#         temp_file.close()
#         return temp_file.name, preview_data
    
#     except Exception as e:
#         logger.error(f"PowerPoint creation error: {str(e)}")
#         raise Exception(f"Failed to create PowerPoint: {str(e)}")

# @app.route('/generate_ppt', methods=['POST'])
# def generate_ppt():
#     try:
#         data = request.json
#         topic = data.get('topic')
#         num_slides = int(data.get('num_slides', 3))
#         template = data.get('template', 'default')
#         if not topic:
#             return jsonify({"error": "Topic is required"}), 400
#         if num_slides < 1 or num_slides > 20:
#             return jsonify({"error": "Number of slides must be between 1 and 20"}), 400
#         logger.info(f"Generating content for topic: {topic} with {num_slides} slides using template: {template}")
#         content_data = generate_text_content(topic, num_slides)
#         image_prompts = {}
#         try:
#             logger.info("Generating title image prompt")
#             title_image_prompt = generate_image_prompt(topic)
#             if title_image_prompt:
#                 image_prompts["title"] = title_image_prompt
#             logger.info("Generating slide image prompts")
#             for i, slide_data in enumerate(content_data.get("slides", [])):
#                 slide_title = slide_data.get("title", "")
#                 slide_image_prompt = generate_image_prompt(f"{topic} - {slide_title}")
#                 if slide_image_prompt:
#                     image_prompts[str(i)] = slide_image_prompt
#         except Exception as e:
#             logger.warning(f"Image prompt generation failed: {str(e)}")
#         logger.info(f"Creating PowerPoint presentation with template: {template}")
#         ppt_file, preview_data = create_presentation(content_data, image_prompts, template)
#         unique_id = uuid.uuid4().hex[:8]
#         filename = f"{topic.replace(' ', '_')}_{unique_id}.pptx"
#         user_filename = os.path.join("static", "downloads", filename)
#         os.makedirs(os.path.dirname(user_filename), exist_ok=True)
#         with open(ppt_file, 'rb') as src, open(user_filename, 'wb') as dst:
#             dst.write(src.read())
#         os.unlink(ppt_file)
#         return jsonify({
#             "success": True,
#             "filename": filename,
#             "download_url": f"/static/downloads/{filename}",
#             "content": content_data,
#             "image_prompts": image_prompts,
#             "template": template,
#             "preview_data": preview_data
#         })
#     except Exception as e:
#         logger.error(f"Error processing request: {str(e)}")
#         return jsonify({"error": str(e)}), 500

# @app.route('/update_ppt', methods=['POST'])
# def update_ppt():
#     try:
#         data = request.json
#         content_data = data.get('content')
#         image_prompts = data.get('image_prompts', {})
#         template = data.get('template', 'default')
#         if not content_data or 'title' not in content_data or 'slides' not in content_data:
#             return jsonify({"error": "Invalid presentation content"}), 400
#         logger.info("Creating updated PowerPoint presentation")
#         ppt_file, preview_data = create_presentation(content_data, image_prompts, template)
#         unique_id = uuid.uuid4().hex[:8]
#         topic = content_data.get("title", "Presentation").replace(' ', '_')
#         filename = f"{topic}_{unique_id}.pptx"
#         user_filename = os.path.join("static", "downloads", filename)
#         os.makedirs(os.path.dirname(user_filename), exist_ok=True)
#         with open(ppt_file, 'rb') as src, open(user_filename, 'wb') as dst:
#             dst.write(src.read())
#         os.unlink(ppt_file)
#         return jsonify({
#             "success": True,
#             "filename": filename,
#             "download_url": f"/static/downloads/{filename}",
#             "preview_data": preview_data
#         })
#     except Exception as e:
#         logger.error(f"Error updating presentation: {str(e)}")
#         return jsonify({"error": str(e)}), 500

# @app.route('/')
# def index():
#     return app.send_static_file('index.html')

# @app.route('/static/<path:path>')
# def serve_static(path):
#     logger.debug(f"Serving static file: {path}")
#     return app.send_static_file(path)

# @app.route('/get_templates', methods=['GET'])
# def get_templates():
#     try:
#         templates = template_manager.get_all_templates()
#         template_response = {}
#         for key, template in templates.items():
#             template_response[key] = {
#                 "name": template.get('name', key),
#                 "description": template.get('description', ''),
#                 "preview_image": template.get('preview_image', ''),
#                 "styles": template.get('styles', {})
#             }
#         logger.info(f"Returning {len(template_response)} templates")
#         return jsonify({
#             "success": True,
#             "templates": template_response
#         })
#     except Exception as e:
#         logger.error(f"Error retrieving templates: {str(e)}")
#         return jsonify({"error": "Failed to retrieve templates"}), 500

# @app.route('/download/<filename>')
# def download_file(filename):
#     file_path = os.path.join("static", "downloads", filename)
#     if not os.path.exists(file_path):
#         logger.error(f"Download file not found: {file_path}")
#         return jsonify({"error": "File not found"}), 404
#     logger.info(f"Downloading file: {file_path}")
#     return send_file(file_path, as_attachment=True)

# if __name__ == '__main__':
#     os.makedirs(os.path.join("static", "downloads"), exist_ok=True)
#     app.run(debug=True)



# from flask import Flask, request, jsonify, send_file, redirect, url_for, render_template, session
# from pptx import Presentation
# from pptx.util import Inches, Pt
# from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
# from pptx.dml.color import RGBColor
# import requests
# import os
# import json
# import tempfile
# import uuid
# import logging
# from template_manager import TemplateManager
# from werkzeug.security import generate_password_hash, check_password_hash
# import sqlite3
# from io import BytesIO
# from flask_cors import CORS

# app = Flask(__name__)
# CORS(app)
# template_manager = TemplateManager()

# # Configure logging
# logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
# logger = logging.getLogger(__name__)

# app.secret_key = 'your_secret_key'

# def get_db():
#     conn = sqlite3.connect('users.db')
#     conn.row_factory = sqlite3.Row
#     return conn

# @app.route('/register', methods=['GET', 'POST'])
# def register():
#     if request.method == 'POST':
#         username = request.form['username']
#         email = request.form['email']
#         password = request.form['password']
#         hashed_password = generate_password_hash(password)
#         try:
#             conn = get_db()
#             c = conn.cursor()
#             c.execute('INSERT INTO users (username, email, password) VALUES (?, ?, ?)',
#                       (username, email, hashed_password))
#             conn.commit()
#             conn.close()
#             return redirect(url_for('login'))
#         except sqlite3.IntegrityError:
#             conn.close()
#             return render_template('register.html', error='Username or email already exists')
#     return render_template('register.html')

# @app.route('/login', methods=['GET', 'POST'])
# def login():
#     if request.method == 'POST':
#         email = request.form['email']
#         password = request.form['password']
#         conn = get_db()
#         c = conn.cursor()
#         c.execute('SELECT * FROM users WHERE email = ?', (email,))
#         user = c.fetchone()
#         conn.close()
#         if user and check_password_hash(user['password'], password):
#             session['user_id'] = user['id']
#             session['username'] = user['username']
#             return redirect(url_for('index'))
#         else:
#             return render_template('login.html', error='Invalid email or password')
#     return render_template('login.html')

# @app.route('/logout')
# def logout():
#     session.pop('user_id', None)
#     session.pop('username', None)
#     return redirect(url_for('login'))

# def login_required(f):
#     def wrapper(*args, **kwargs):
#         if 'user_id' not in session:
#             return redirect(url_for('login'))
#         return f(*args, **kwargs)
#     wrapper.__name__ = f.__name__
#     return wrapper

# OLLAMA_ENDPOINT = "http://localhost:11434/api/generate"

# def generate_text_content(topic, num_slides):
#     try:
#         prompt = f"""Generate a detailed JSON for a presentation about '{topic}' with {num_slides} slides.
#         Each slide should have the following:
#         - A detailed title
#         - At least 5 concise and informative bullet points per slide (if applicable)
#         - Provide some additional explanations or insights for each bullet point
#         - Ensure the content is rich, professional, and informative
#         Format EXACTLY as this JSON structure:
#         {{
#             "title": "Overall Presentation Title",
#             "slides": [
#                 {{
#                     "title": "Slide 1 Title",
#                     "points": [
#                         "Point 1: Detailed explanation or context",
#                         "Point 2: Detailed explanation or context",
#                         "Point 3: Detailed explanation or context",
#                         "Point 4: Additional context or related points",
#                         "Point 5: Further insights or examples"
#                     ]
#                 }},
#                 ...
#             ]
#         }}
#         Requirements:
#         - Use clear, professional language
#         - Ensure each slide has a meaningful title
#         - Create at least 5 detailed, informative bullet points per slide
#         - Provide explanations, context, or examples where relevant
#         - Avoid any markdown, code blocks, or extra formatting
#         """
#         payload = {
#             "model": "llama3.2:1b",
#             "prompt": prompt,
#             "stream": False,
#             "format": "json"
#         }
#         response = requests.post(OLLAMA_ENDPOINT, json=payload)
#         if response.status_code != 200:
#             logger.error(f"Ollama API error: {response.status_code} - {response.text}")
#             raise Exception(f"Ollama API error: {response.status_code}")
#         content = response.json()["response"]
#         if "```json" in content:
#             content = content.split("```json")[1].split("```")[0].strip()
#         elif "```" in content:
#             content = content.split("```")[1].split("```")[0].strip()
#         presentation_data = json.loads(content)
#         if not isinstance(presentation_data, dict) or 'title' not in presentation_data or 'slides' not in presentation_data:
#             raise ValueError("Invalid JSON structure")
#         for slide in presentation_data.get('slides', []):
#             if 'title' not in slide or 'points' not in slide:
#                 raise ValueError("Invalid slide structure")
#         return presentation_data
#     except Exception as e:
#         logger.error(f"Text generation error: {str(e)}")
#         return {
#             "title": topic,
#             "slides": [
#                 {
#                     "title": f"Introduction to {topic}",
#                     "points": [
#                         "Overview of the topic with more context and background",
#                         "Key points to discuss with additional details",
#                         "Importance and relevance with examples or data"
#                     ]
#                 },
#                 {
#                     "title": "Main Concepts",
#                     "points": [
#                         "First main concept with detailed examples",
#                         "Second main concept with further elaboration",
#                         "Third main concept with supporting data or case studies"
#                     ]
#                 },
#                 {
#                     "title": "Conclusion",
#                     "points": [
#                         "Summary of key takeaways with insights",
#                         "Future implications with potential applications",
#                         "Call to action with a proposed next step or idea"
#                     ]
#                 }
#             ]
#         }

# def generate_image_prompt(prompt):
#     return f"Professional presentation image related to: {prompt}"

# def create_presentation(content_data, image_prompts=None, template="default"):
#     try:
#         template_config = template_manager.get_template(template) or template_manager.get_template('default')
#         styles = template_config.get('styles', {})
#         title_slide_styles = styles.get('title_slide', {})
#         content_slide_styles = styles.get('content_slide', {})
#         image_slide_styles = styles.get('image_slide', {})
        
#         # Log preview image
#         preview_image = template_config.get('preview_image', '')
#         preview_image_path = os.path.join('static', preview_image)
#         if preview_image and os.path.exists(preview_image_path):
#             logger.info(f"Preview image found for template {template}: {preview_image_path}")
#         else:
#             logger.warning(f"Preview image not found for template {template}: {preview_image_path}")
        
#         preview_data = {
#             "title": content_data.get("title", "Presentation"),
#             "template": template,
#             "styles": {
#                 "title_slide": {
#                     "background": title_slide_styles.get('background', {'type': 'solid', 'color': {'r': 240, 'g': 240, 'b': 240}}),
#                     "background_image": title_slide_styles.get('background_image', ''),
#                     "title_font": title_slide_styles.get('title_font', {'name': 'Calibri', 'size': 44, 'color': {'r': 0, 'g': 0, 'b': 0}, 'bold': True, 'alignment': 'center'}),
#                     "image_position": title_slide_styles.get('image_position', {'left': 2.5, 'top': 4.0, 'width': 5.0, 'height': 2.5})
#                 },
#                 "content_slide": {
#                     "background": content_slide_styles.get('background', {'type': 'solid', 'color': {'r': 255, 'g': 255, 'b': 255}}),
#                     "background_image": content_slide_styles.get('background_image', ''),
#                     "title_font": content_slide_styles.get('title_font', {'name': 'Calibri', 'size': 32, 'color': {'r': 0, 'g': 0, 'b': 0}, 'bold': True, 'alignment': 'left'}),
#                     "body_font": content_slide_styles.get('body_font', {'name': 'Calibri', 'size': 18, 'color': {'r': 50, 'g': 50, 'b': 50}, 'alignment': 'left'}),
#                     "image_position": content_slide_styles.get('image_position', {'left': 6.0, 'top': 1.5, 'width': 3.5, 'height': 4.5})
#                 },
#                 "image_slide": {
#                     "fill_color": image_slide_styles.get('fill_color', {'r': 245, 'g': 245, 'b': 245}),
#                     "border_color": image_slide_styles.get('border_color', {'r': 200, 'g': 200, 'b': 200}),
#                     "border_width": image_slide_styles.get('border_width', 1.5),
#                     "border_style": image_slide_styles.get('border_style', 'dashed')
#                 }
#             },
#             "slides": []
#         }
        
#         prs = Presentation()
        
#         # Title Slide
#         blank_slide_layout = prs.slide_layouts[6]
#         title_slide = prs.slides.add_slide(blank_slide_layout)
        
#         background_settings = title_slide_styles.get('background', {})
#         bg_image = title_slide_styles.get('background_image', '')
#         background = title_slide.background
#         fill = background.fill
#         # Title Slide - Background Image
#         if bg_image:
#             bg_image_path = os.path.join('static', bg_image)
#             if os.path.exists(bg_image_path):
#                 logger.info(f"Applying background image for title slide: {bg_image_path}")
#                 fill.picture(bg_image_path)  # Correct usage
#             else:
#                 logger.error(f"Background image not found for title slide: {bg_image_path}, falling back to solid color")
#                 fill.solid()
#                 bg_color = background_settings.get('color', {'r': 240, 'g': 240, 'b': 240}) if background_settings.get('type') == 'solid' else background_settings.get('gradient_start', {'r': 240, 'g': 240, 'b': 240})
#                 fill.fore_color.rgb = RGBColor(bg_color['r'], bg_color['g'], bg_color['b'])

#         else:
#             logger.debug(f"No background image specified for title slide, using {background_settings.get('type', 'solid')} background")
#             fill.solid()
#             bg_color = background_settings.get('color', {'r': 240, 'g': 240, 'b': 240}) if background_settings.get('type') == 'solid' else background_settings.get('gradient_start', {'r': 240, 'g': 240, 'b': 240})
#             fill.fore_color.rgb = RGBColor(bg_color['r'], bg_color['g'], bg_color['b'])
        
#         left = Inches(1.0)
#         top = Inches(2.0)
#         width = Inches(8.0)
#         height = Inches(1.5)
#         title_box = title_slide.shapes.add_textbox(left, top, width, height)
#         title_frame = title_box.text_frame
#         title_frame.text = content_data.get("title", "Presentation")
#         title_para = title_frame.paragraphs[0]
#         title_font_settings = title_slide_styles.get('title_font', {})
#         title_para.font.name = title_font_settings.get('name', 'Calibri')
#         title_para.font.size = Pt(title_font_settings.get('size', 44))
#         title_color = title_font_settings.get('color', {'r': 0, 'g': 0, 'b': 0})
#         title_para.font.color.rgb = RGBColor(title_color['r'], title_color['g'], title_color['b'])
#         title_para.font.bold = title_font_settings.get('bold', True)
#         title_para.alignment = PP_ALIGN.CENTER
        
#         title_image_style = {}
#         if image_prompts and "title" in image_prompts:
#             image_position = title_slide_styles.get('image_position', {'left': 2.5, 'top': 4.0, 'width': 5.0, 'height': 2.5})
#             img_left = Inches(image_position.get('left', 2.5))
#             img_top = Inches(image_position.get('top', 4.0))
#             img_width = Inches(image_position.get('width', 5.0))
#             img_height = Inches(image_position.get('height', 2.5))
#             img_placeholder = title_slide.shapes.add_shape(1, img_left, img_top, img_width, img_height)
#             img_placeholder.fill.solid()
#             fill_color = image_slide_styles.get('fill_color', {'r': 245, 'g': 245, 'b': 245})
#             img_placeholder.fill.fore_color.rgb = RGBColor(fill_color['r'], fill_color['g'], fill_color['b'])
#             border_color = image_slide_styles.get('border_color', {'r': 200, 'g': 200, 'b': 200})
#             img_placeholder.line.color.rgb = RGBColor(border_color['r'], border_color['g'], border_color['b'])
#             img_placeholder.line.width = Pt(image_slide_styles.get('border_width', 1.5))
#             img_placeholder.line.dash_style = 2 if image_slide_styles.get('border_style', 'dashed') == 'dashed' else 1
#             text_frame = img_placeholder.text_frame
#             text_frame.word_wrap = True
#             text_frame.vertical_anchor = MSO_ANCHOR.MIDDLE
#             icon_p = text_frame.add_paragraph()
#             icon_p.text = "🖼️"
#             icon_p.alignment = PP_ALIGN.CENTER
#             icon_p.font.size = Pt(48)
#             icon_p.space_after = Pt(10)
#             prompt_p = text_frame.add_paragraph()
#             prompt_p.text = image_prompts['title']
#             prompt_p.alignment = PP_ALIGN.CENTER
#             prompt_p.font.italic = True
#             prompt_p.font.size = Pt(14)
#             prompt_p.font.color.rgb = RGBColor(100, 100, 100)
#             title_image_style = {
#                 "left": image_position.get('left', 2.5),
#                 "top": image_position.get('top', 4.0),
#                 "width": image_position.get('width', 5.0),
#                 "height": image_position.get('height', 2.5),
#                 "fill_color": fill_color,
#                 "border_color": border_color,
#                 "border_width": image_slide_styles.get('border_width', 1.5),
#                 "border_style": image_slide_styles.get('border_style', 'dashed')
#             }
        
#         preview_data["slides"].append({
#             "type": "title",
#             "title": content_data.get("title", "Presentation"),
#             "has_image": "title" in image_prompts if image_prompts else False,
#             "image_prompt": image_prompts.get("title") if image_prompts else None,
#             "image_style": title_image_style
#         })
        
#         # Content Slides
#         for i, slide_data in enumerate(content_data.get("slides", [])):
#             slide_index = str(i)
#             content_slide = prs.slides.add_slide(blank_slide_layout)
#             background_settings = content_slide_styles.get('background', {})
#             bg_image = content_slide_styles.get('background_image', '')
#             background = content_slide.background
#             fill = background.fill
#             # Title Slide - Background Image
#             if bg_image:
#                 bg_image_path = os.path.join('static', bg_image)
#                 if os.path.exists(bg_image_path):
#                     logger.info(f"Applying background image for title slide: {bg_image_path}")
#                     fill.picture(bg_image_path)  # Correct usage
#                 else:
#                     logger.error(f"Background image not found for title slide: {bg_image_path}, falling back to solid color")
#                     fill.solid()
#                     bg_color = background_settings.get('color', {'r': 240, 'g': 240, 'b': 240}) if background_settings.get('type') == 'solid' else background_settings.get('gradient_start', {'r': 240, 'g': 240, 'b': 240})
#                     fill.fore_color.rgb = RGBColor(bg_color['r'], bg_color['g'], bg_color['b'])

#             else:
#                 logger.debug(f"No background image specified for content slide {i+1}, using {background_settings.get('type', 'solid')} background")
#                 fill.solid()
#                 bg_color = background_settings.get('color', {'r': 255, 'g': 255, 'b': 255}) if background_settings.get('type') == 'solid' else background_settings.get('gradient_start', {'r': 255, 'g': 255, 'b': 255})
#                 fill.fore_color.rgb = RGBColor(bg_color['r'], bg_color['g'], bg_color['b'])
            
#             title_left = Inches(0.5)
#             title_top = Inches(0.5)
#             title_width = Inches(9.0)
#             title_height = Inches(0.8)
#             title_box = content_slide.shapes.add_textbox(title_left, title_top, title_width, title_height)
#             title_frame = title_box.text_frame
#             title_frame.text = slide_data.get("title", f"Slide {i+1}")
#             title_para = title_frame.paragraphs[0]
#             title_font = content_slide_styles.get('title_font', {})
#             title_para.font.name = title_font.get('name', 'Calibri')
#             title_para.font.size = Pt(title_font.get('size', 32))
#             title_color = title_font.get('color', {'r': 0, 'g': 0, 'b': 0})
#             title_para.font.color.rgb = RGBColor(title_color['r'], title_color['g'], title_color['b'])
#             title_para.font.bold = title_font.get('bold', True)
#             title_para.alignment = {
#                 'center': PP_ALIGN.CENTER,
#                 'left': PP_ALIGN.LEFT,
#                 'right': PP_ALIGN.RIGHT
#             }.get(title_font.get('alignment', 'left'), PP_ALIGN.LEFT)
            
#             points_styling = []
#             if slide_data.get("points", []):
#                 content_left = Inches(0.5)
#                 content_top = Inches(1.5)
#                 content_width = Inches(5.0)
#                 content_height = Inches(4.5)
#                 content_box = content_slide.shapes.add_textbox(content_left, content_top, content_width, content_height)
#                 text_frame = content_box.text_frame
#                 text_frame.word_wrap = True
#                 body_font = content_slide_styles.get('body_font', {})
#                 for point in slide_data.get("points", []):
#                     if text_frame.paragraphs and text_frame.paragraphs[0].text == "":
#                         p = text_frame.paragraphs[0]
#                     else:
#                         p = text_frame.add_paragraph()
#                     p.text = "• " + point
#                     p.font.name = body_font.get('name', 'Calibri')
#                     p.font.size = Pt(body_font.get('size', 18))
#                     body_color = body_font.get('color', {'r': 50, 'g': 50, 'b': 50})
#                     p.font.color.rgb = RGBColor(body_color['r'], body_color['g'], body_color['b'])
#                     p.space_before = Pt(6)
#                     p.space_after = Pt(6)
#                     p.alignment = {
#                         'center': PP_ALIGN.CENTER,
#                         'left': PP_ALIGN.LEFT,
#                         'right': PP_ALIGN.RIGHT
#                     }.get(body_font.get('alignment', 'left'), PP_ALIGN.LEFT)
#                     points_styling.append({
#                         "text": point,
#                         "level": 0,
#                         "font_name": body_font.get('name', 'Calibri'),
#                         "font_size": body_font.get('size', 18),
#                         "color": body_color,
#                         "alignment": body_font.get('alignment', 'left'),
#                         "space_before": 6,
#                         "space_after": 6
#                     })
            
#             content_image_style = {}
#             if image_prompts and slide_index in image_prompts:
#                 image_position = content_slide_styles.get('image_position', {'left': 6.0, 'top': 1.5, 'width': 3.5, 'height': 4.5})
#                 img_left = Inches(image_position.get('left', 6.0))
#                 img_top = Inches(image_position.get('top', 1.5))
#                 img_width = Inches(image_position.get('width', 3.5))
#                 img_height = Inches(image_position.get('height', 4.5))
#                 img_placeholder = content_slide.shapes.add_shape(1, img_left, img_top, img_width, img_height)
#                 img_placeholder.fill.solid()
#                 fill_color = image_slide_styles.get('fill_color', {'r': 245, 'g': 245, 'b': 245})
#                 img_placeholder.fill.fore_color.rgb = RGBColor(fill_color['r'], fill_color['g'], fill_color['b'])
#                 border_color = image_slide_styles.get('border_color', {'r': 200, 'g': 200, 'b': 200})
#                 img_placeholder.line.color.rgb = RGBColor(border_color['r'], border_color['g'], border_color['b'])
#                 img_placeholder.line.width = Pt(image_slide_styles.get('border_width', 1.5))
#                 img_placeholder.line.dash_style = 2 if image_slide_styles.get('border_style', 'dashed') == 'dashed' else 1
#                 text_frame = img_placeholder.text_frame
#                 text_frame.word_wrap = True
#                 text_frame.vertical_anchor = MSO_ANCHOR.MIDDLE
#                 icon_p = text_frame.add_paragraph()
#                 icon_p.text = "🖼️"
#                 icon_p.alignment = PP_ALIGN.CENTER
#                 icon_p.font.size = Pt(48)
#                 icon_p.space_after = Pt(10)
#                 prompt_p = text_frame.add_paragraph()
#                 prompt_p.text = image_prompts[slide_index]
#                 prompt_p.alignment = PP_ALIGN.CENTER
#                 prompt_p.font.italic = True
#                 prompt_p.font.size = Pt(14)
#                 prompt_p.font.color.rgb = RGBColor(100, 100, 100)
#                 content_image_style = {
#                     "left": image_position.get('left', 6.0),
#                     "top": image_position.get('top', 1.5),
#                     "width": image_position.get('width', 3.5),
#                     "height": image_position.get('height', 4.5),
#                     "fill_color": fill_color,
#                     "border_color": border_color,
#                     "border_width": image_slide_styles.get('border_width', 1.5),
#                     "border_style": image_slide_styles.get('border_style', 'dashed')
#                 }
            
#             preview_data["slides"].append({
#                 "type": "content",
#                 "title": slide_data.get("title", f"Slide {i+1}"),
#                 "points": slide_data.get("points", []),
#                 "points_styling": points_styling,
#                 "has_image": slide_index in image_prompts if image_prompts else False,
#                 "image_prompt": image_prompts.get(slide_index) if image_prompts else None,
#                 "image_style": content_image_style
#             })
        
#         temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".pptx")
#         prs.save(temp_file.name)
#         temp_file.close()
#         return temp_file.name, preview_data
    
#     except Exception as e:
#         logger.error(f"PowerPoint creation error: {str(e)}")
#         raise Exception(f"Failed to create PowerPoint: {str(e)}")

# @app.route('/generate_ppt', methods=['POST'])
# def generate_ppt():
#     try:
#         data = request.json
#         topic = data.get('topic')
#         num_slides = int(data.get('num_slides', 3))
#         template = data.get('template', 'default')
#         if not topic:
#             return jsonify({"error": "Topic is required"}), 400
#         if num_slides < 1 or num_slides > 20:
#             return jsonify({"error": "Number of slides must be between 1 and 20"}), 400
#         logger.info(f"Generating content for topic: {topic} with {num_slides} slides using template: {template}")
#         content_data = generate_text_content(topic, num_slides)
#         image_prompts = {}
#         try:
#             logger.info("Generating title image prompt")
#             title_image_prompt = generate_image_prompt(topic)
#             if title_image_prompt:
#                 image_prompts["title"] = title_image_prompt
#             logger.info("Generating slide image prompts")
#             for i, slide_data in enumerate(content_data.get("slides", [])):
#                 slide_title = slide_data.get("title", "")
#                 slide_image_prompt = generate_image_prompt(f"{topic} - {slide_title}")
#                 if slide_image_prompt:
#                     image_prompts[str(i)] = slide_image_prompt
#         except Exception as e:
#             logger.warning(f"Image prompt generation failed: {str(e)}")
#         logger.info(f"Creating PowerPoint presentation with template: {template}")
#         ppt_file, preview_data = create_presentation(content_data, image_prompts, template)
#         unique_id = uuid.uuid4().hex[:8]
#         filename = f"{topic.replace(' ', '_')}_{unique_id}.pptx"
#         user_filename = os.path.join("static", "downloads", filename)
#         os.makedirs(os.path.dirname(user_filename), exist_ok=True)
#         with open(ppt_file, 'rb') as src, open(user_filename, 'wb') as dst:
#             dst.write(src.read())
#         os.unlink(ppt_file)
#         return jsonify({
#             "success": True,
#             "filename": filename,
#             "download_url": f"/static/downloads/{filename}",
#             "content": content_data,
#             "image_prompts": image_prompts,
#             "template": template,
#             "preview_data": preview_data
#         })
#     except Exception as e:
#         logger.error(f"Error processing request: {str(e)}")
#         return jsonify({"error": str(e)}), 500

# @app.route('/update_ppt', methods=['POST'])
# def update_ppt():
#     try:
#         data = request.json
#         content_data = data.get('content')
#         image_prompts = data.get('image_prompts', {})
#         template = data.get('template', 'default')
#         if not content_data or 'title' not in content_data or 'slides' not in content_data:
#             return jsonify({"error": "Invalid presentation content"}), 400
#         logger.info("Creating updated PowerPoint presentation")
#         ppt_file, preview_data = create_presentation(content_data, image_prompts, template)
#         unique_id = uuid.uuid4().hex[:8]
#         topic = content_data.get("title", "Presentation").replace(' ', '_')
#         filename = f"{topic}_{unique_id}.pptx"
#         user_filename = os.path.join("static", "downloads", filename)
#         os.makedirs(os.path.dirname(user_filename), exist_ok=True)
#         with open(ppt_file, 'rb') as src, open(user_filename, 'wb') as dst:
#             dst.write(src.read())
#         os.unlink(ppt_file)
#         return jsonify({
#             "success": True,
#             "filename": filename,
#             "download_url": f"/static/downloads/{filename}",
#             "preview_data": preview_data
#         })
#     except Exception as e:
#         logger.error(f"Error updating presentation: {str(e)}")
#         return jsonify({"error": str(e)}), 500

# @app.route('/')
# def index():
#     return app.send_static_file('index.html')

# @app.route('/static/<path:path>')
# def serve_static(path):
#     logger.debug(f"Serving static file: {path}")
#     return app.send_static_file(path)

# @app.route('/get_templates', methods=['GET'])
# def get_templates():
#     try:
#         templates = template_manager.get_all_templates()
#         template_response = {}
#         for key, template in templates.items():
#             template_response[key] = {
#                 "name": template.get('name', key),
#                 "description": template.get('description', ''),
#                 "preview_image": template.get('preview_image', ''),
#                 "styles": template.get('styles', {})
#             }
#         logger.info(f"Returning {len(template_response)} templates")
#         return jsonify({
#             "success": True,
#             "templates": template_response
#         })
#     except Exception as e:
#         logger.error(f"Error retrieving templates: {str(e)}")
#         return jsonify({"error": "Failed to retrieve templates"}), 500

# @app.route('/download/<filename>')
# def download_file(filename):
#     file_path = os.path.join("static", "downloads", filename)
#     if not os.path.exists(file_path):
#         logger.error(f"Download file not found: {file_path}")
#         return jsonify({"error": "File not found"}), 404
#     logger.info(f"Downloading file: {file_path}")
#     return send_file(file_path, as_attachment=True)

# if __name__ == '__main__':
#     os.makedirs(os.path.join("static", "downloads"), exist_ok=True)
#     app.run(debug=True)

# # from flask import Flask, request, jsonify, send_file, redirect, url_for, render_template, session
# # from pptx import Presentation
# # from pptx.util import Inches, Pt
# # from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
# # from pptx.dml.color import RGBColor
# # import requests
# # import os
# # import json
# # import tempfile
# # import uuid
# # import logging
# # from template_manager import TemplateManager
# # from werkzeug.security import generate_password_hash, check_password_hash
# # import sqlite3

# # from io import BytesIO
# # from flask_cors import CORS
# # app = Flask(__name__)
# # CORS(app)  # Enable CORS for all routes
# # template_manager = TemplateManager()

# # # Configure logging
# # logging.basicConfig(level=logging.INFO)
# # logger = logging.getLogger(__name__)

# # app.secret_key = 'your_secret_key'  # Replace with a secure key

# # # Database connection helper
# # def get_db():
# #     conn = sqlite3.connect('users.db')
# #     conn.row_factory = sqlite3.Row
# #     return conn

# # # Authentication routes
# # @app.route('/register', methods=['GET', 'POST'])
# # def register():
# #     if request.method == 'POST':
# #         username = request.form['username']
# #         email = request.form['email']
# #         password = request.form['password']
        
# #         # Hash the password
# #         hashed_password = generate_password_hash(password)
        
# #         try:
# #             conn = get_db()
# #             c = conn.cursor()
# #             c.execute('INSERT INTO users (username, email, password) VALUES (?, ?, ?)',
# #                       (username, email, hashed_password))
# #             conn.commit()
# #             conn.close()
# #             return redirect(url_for('login'))
# #         except sqlite3.IntegrityError:
# #             conn.close()
# #             return render_template('register.html', error='Username or email already exists')
    
# #     return render_template('register.html')

# # @app.route('/login', methods=['GET', 'POST'])
# # def login():
# #     if request.method == 'POST':
# #         email = request.form['email']
# #         password = request.form['password']
        
# #         conn = get_db()
# #         c = conn.cursor()
# #         c.execute('SELECT * FROM users WHERE email = ?', (email,))
# #         user = c.fetchone()
# #         conn.close()
        
# #         if user and check_password_hash(user['password'], password):
# #             session['user_id'] = user['id']
# #             session['username'] = user['username']
# #             return redirect(url_for('index'))
# #         else:
# #             return render_template('login.html', error='Invalid email or password')
    
# #     return render_template('login.html')

# # @app.route('/logout')
# # def logout():
# #     session.pop('user_id', None)
# #     session.pop('username', None)
# #     return redirect(url_for('login'))

# # # Protect routes by checking if user is logged in
# # def login_required(f):
# #     def wrapper(*args, **kwargs):
# #         if 'user_id' not in session:
# #             return redirect(url_for('login'))
# #         return f(*args, **kwargs)
# #     wrapper.__name__ = f.__name__
# #     return wrapper

# # # Local Ollama endpoint
# # OLLAMA_ENDPOINT = "http://localhost:11434/api/generate"

# # def generate_text_content(topic, num_slides):
# #     """Generate slide content using local Ollama model"""
# #     try:
# #         # Modified prompt to encourage the generation of more detailed text
# #         prompt = f"""Generate a detailed JSON for a presentation about '{topic}' with {num_slides} slides.
# #         Each slide should have the following:
# #         - A detailed title
# #         - At least 5 concise and informative bullet points per slide (if applicable)
# #         - Provide some additional explanations or insights for each bullet point
# #         - Ensure the content is rich, professional, and informative
        
# #         Format EXACTLY as this JSON structure:
# #         {{
# #             "title": "Overall Presentation Title",
# #             "slides": [
# #                 {{
# #                     "title": "Slide 1 Title",
# #                     "points": [
# #                         "Point 1: Detailed explanation or context",
# #                         "Point 2: Detailed explanation or context",
# #                         "Point 3: Detailed explanation or context",
# #                         "Point 4: Additional context or related points",
# #                         "Point 5: Further insights or examples"
# #                     ]
# #                 }},
# #                 ... (additional slides with more detailed points)
# #             ]
# #         }}
        
# #         Requirements:
# #         - Use clear, professional language
# #         - Ensure each slide has a meaningful title
# #         - Create at least 5 detailed, informative bullet points per slide
# #         - Provide explanations, context, or examples where relevant
# #         - Avoid any markdown, code blocks, or extra formatting
# #         """
        
# #         payload = {
# #             "model": "llama3.2:1b",  # Adjust as needed
# #             "prompt": prompt,
# #             "stream": False,
# #             "format": "json"  # Request JSON format
# #         }
        
# #         response = requests.post(
# #             OLLAMA_ENDPOINT,
# #             json=payload
# #         )
        
# #         if response.status_code != 200:
# #             logger.error(f"Ollama API error: {response.status_code} - {response.text}")
# #             raise Exception(f"Ollama API error: {response.status_code}")
            
# #         content = response.json()["response"]
        
# #         # Additional parsing safeguards
# #         try:
# #             # Remove any potential markdown code blocks
# #             if "```json" in content:
# #                 content = content.split("```json")[1].split("```")[0].strip()
# #             elif "```" in content:
# #                 content = content.split("```")[1].split("```")[0].strip()
            
# #             # Parse the JSON
# #             presentation_data = json.loads(content)
            
# #             # Validate the structure
# #             if not isinstance(presentation_data, dict):
# #                 raise ValueError("Invalid JSON structure")
            
# #             if 'title' not in presentation_data or 'slides' not in presentation_data:
# #                 raise ValueError("Missing required keys")
            
# #             # Ensure slides have required structure
# #             for slide in presentation_data.get('slides', []):
# #                 if 'title' not in slide or 'points' not in slide:
# #                     raise ValueError("Invalid slide structure")
            
# #             return presentation_data
        
# #         except (json.JSONDecodeError, ValueError) as parsing_error:
# #             logger.error(f"JSON parsing error: {parsing_error}")
# #             logger.debug(f"Received content: {content}")
            
# #             # Fallback content generation with more detailed bullet points
# #             return {
# #                 "title": topic,
# #                 "slides": [
# #                     {
# #                         "title": f"Introduction to {topic}",
# #                         "points": [
# #                             "Overview of the topic with more context and background",
# #                             "Key points to discuss with additional details",
# #                             "Importance and relevance with examples or data"
# #                         ]
# #                     },
# #                     {
# #                         "title": "Main Concepts",
# #                         "points": [
# #                             "First main concept with detailed examples",
# #                             "Second main concept with further elaboration",
# #                             "Third main concept with supporting data or case studies"
# #                         ]
# #                     },
# #                     {
# #                         "title": "Conclusion",
# #                         "points": [
# #                             "Summary of key takeaways with insights",
# #                             "Future implications with potential applications",
# #                             "Call to action with a proposed next step or idea"
# #                         ]
# #                     }
# #                 ]
# #             }
    
# #     except Exception as e:
# #         logger.error(f"Text generation error: {str(e)}")
# #         raise Exception(f"Failed to generate text content: {str(e)}")


# # def generate_image_prompt(prompt):
# #     """Instead of generating an image, return the prompt that would have been used"""
# #     image_prompt = f"Professional presentation image related to: {prompt}"
# #     return image_prompt

# # def create_presentation(content_data, image_prompts=None, template="default"):
# #     """Create a PowerPoint presentation that looks EXACTLY like the HTML preview.
# #     Returns both the file path and a preview JSON structure for HTML rendering."""
# #     try:
# #         # Load template configuration
# #         template_config = template_manager.get_template(template)
# #         if not template_config:
# #             logger.warning(f"Template {template} not found, using default")
# #             template_config = template_manager.get_template('default')
        
# #         # Extract styling
# #         styles = template_config.get('styles', {})
# #         title_slide_styles = styles.get('title_slide', {})
# #         content_slide_styles = styles.get('content_slide', {})
        
# #         # Create a preview data structure that will match the PowerPoint styling
# #         preview_data = {
# #             "title": content_data.get("title", "Presentation"),
# #             "template": template,
# #             "styles": {
# #                 "title_slide": {
# #                     "background": title_slide_styles.get('background', {
# #                         'type': 'solid',
# #                         'color': {'r': 240, 'g': 240, 'b': 240}
# #                     }),
# #                     "title_font": title_slide_styles.get('title_font', {
# #                         'name': 'Calibri',
# #                         'size': 44,
# #                         'color': {'r': 0, 'g': 0, 'b': 0},
# #                         'bold': True,
# #                         'alignment': 'center'
# #                     })
# #                 },
# #                 "content_slide": {
# #                     "background": content_slide_styles.get('background', {
# #                         'type': 'solid',
# #                         'color': {'r': 255, 'g': 255, 'b': 255}
# #                     }),
# #                     "title_font": content_slide_styles.get('title_font', {
# #                         'name': 'Calibri',
# #                         'size': 32,
# #                         'color': {'r': 0, 'g': 0, 'b': 0},
# #                         'bold': True,
# #                         'alignment': 'left'
# #                     }),
# #                     "body_font": content_slide_styles.get('body_font', {
# #                         'name': 'Calibri',
# #                         'size': 18,
# #                         'color': {'r': 50, 'g': 50, 'b': 50},
# #                         'alignment': 'left'
# #                     })
# #                 },
# #                 "image_slide": styles.get('image_slide', {})
# #             },
# #             "slides": []
# #         }
        
# #         # Create a blank presentation
# #         prs = Presentation()
        
# #         # ---------- TITLE SLIDE ----------
# #         blank_slide_layout = prs.slide_layouts[6]  # Usually the blank layout
# #         title_slide = prs.slides.add_slide(blank_slide_layout)
        
# #         # Apply title slide background
# #         background_settings = title_slide_styles.get('background', {})
# #         if background_settings.get('type') == 'solid':
# #             background = title_slide.background
# #             fill = background.fill
# #             fill.solid()
# #             bg_color = background_settings.get('color', {'r': 240, 'g': 240, 'b': 240})
# #             fill.fore_color.rgb = RGBColor(bg_color['r'], bg_color['g'], bg_color['b'])
# #         else:
# #             background = title_slide.background
# #             fill = background.fill
# #             fill.solid()
# #             fill.fore_color.rgb = RGBColor(240, 240, 240)
        
# #         # Add presentation title
# #         left = Inches(1.0)
# #         top = Inches(2.0)
# #         width = Inches(8.0)
# #         height = Inches(1.5)
# #         title_box = title_slide.shapes.add_textbox(left, top, width, height)
        
# #         title_frame = title_box.text_frame
# #         title_frame.text = content_data.get("title", "Presentation")
# #         title_para = title_frame.paragraphs[0]
        
# #         title_font_settings = title_slide_styles.get('title_font', {})
# #         title_para.font.name = title_font_settings.get('name', 'Calibri')
# #         title_para.font.size = Pt(title_font_settings.get('size', 44))
# #         title_color = title_font_settings.get('color', {'r': 0, 'g': 0, 'b': 0})
# #         title_para.font.color.rgb = RGBColor(title_color['r'], title_color['g'], title_color['b'])
# #         title_para.font.bold = title_font_settings.get('bold', True)
# #         title_para.alignment = PP_ALIGN.CENTER
        
# #         # Add image placeholder if title slide has an image prompt
# #         title_image_style = {}
# #         if image_prompts and "title" in image_prompts:
# #             img_left = Inches(2.5)
# #             img_top = Inches(4.0)
# #             img_width = Inches(5.0)
# #             img_height = Inches(2.5)
            
# #             img_placeholder = title_slide.shapes.add_shape(
# #                 1, img_left, img_top, img_width, img_height
# #             )
            
# #             img_placeholder.fill.solid()
# #             img_placeholder.fill.fore_color.rgb = RGBColor(245, 245, 245)
# #             img_placeholder.line.color.rgb = RGBColor(200, 200, 200)
# #             img_placeholder.line.width = Pt(1.5)
# #             img_placeholder.line.dash_style = 2
            
# #             text_frame = img_placeholder.text_frame
# #             text_frame.word_wrap = True
# #             text_frame.vertical_anchor = MSO_ANCHOR.MIDDLE
            
# #             icon_p = text_frame.add_paragraph()
# #             icon_p.text = "🖼️"
# #             icon_p.alignment = PP_ALIGN.CENTER
# #             icon_p.font.size = Pt(48)
# #             icon_p.space_after = Pt(10)
            
# #             prompt_p = text_frame.add_paragraph()
# #             prompt_p.text = image_prompts['title']
# #             prompt_p.alignment = PP_ALIGN.CENTER
# #             prompt_p.font.italic = True
# #             prompt_p.font.size = Pt(14)
# #             prompt_p.font.color.rgb = RGBColor(100, 100, 100)
            
# #             # Store image style for preview
# #             title_image_style = {
# #                 "left": 2.5,
# #                 "top": 4.0,
# #                 "width": 5.0,
# #                 "height": 2.5,
# #                 "fill_color": {"r": 245, "g": 245, "b": 245},
# #                 "border_color": {"r": 200, "g": 200, "b": 200},
# #                 "border_width": 1.5,
# #                 "border_style": "dashed"
# #             }
        
# #         # Add title slide to preview data
# #         preview_data["slides"].append({
# #             "type": "title",
# #             "title": content_data.get("title", "Presentation"),
# #             "has_image": "title" in image_prompts if image_prompts else False,
# #             "image_prompt": image_prompts.get("title") if image_prompts else None,
# #             "image_style": title_image_style
# #         })
        
# #         # ---------- CONTENT SLIDES ----------
# #         for i, slide_data in enumerate(content_data.get("slides", [])):
# #             slide_index = str(i)
            
# #             content_slide = prs.slides.add_slide(blank_slide_layout)
            
# #             background_settings = content_slide_styles.get('background', {})
# #             if background_settings.get('type') == 'solid':
# #                 background = content_slide.background
# #                 fill = background.fill
# #                 fill.solid()
# #                 bg_color = background_settings.get('color', {'r': 255, 'g': 255, 'b': 255})
# #                 fill.fore_color.rgb = RGBColor(bg_color['r'], bg_color['g'], bg_color['b'])
            
# #             title_left = Inches(0.5)
# #             title_top = Inches(0.5)
# #             title_width = Inches(9.0)
# #             title_height = Inches(0.8)
# #             title_box = content_slide.shapes.add_textbox(title_left, title_top, title_width, title_height)
            
# #             title_frame = title_box.text_frame
# #             title_frame.text = slide_data.get("title", f"Slide {i+1}")
# #             title_para = title_frame.paragraphs[0]
            
# #             title_font = content_slide_styles.get('title_font', {})
# #             title_para.font.name = title_font.get('name', 'Calibri')
# #             title_para.font.size = Pt(title_font.get('size', 32))
# #             title_color = title_font.get('color', {'r': 0, 'g': 0, 'b': 0})
# #             title_para.font.color.rgb = RGBColor(title_color['r'], title_color['g'], title_color['b'])
# #             title_para.font.bold = title_font.get('bold', True)
# #             title_para.alignment = {
# #                 'center': PP_ALIGN.CENTER,
# #                 'left': PP_ALIGN.LEFT,
# #                 'right': PP_ALIGN.RIGHT
# #             }.get(title_font.get('alignment', 'left'), PP_ALIGN.LEFT)
            
# #             points_styling = []
# #             if slide_data.get("points", []):
# #                 content_left = Inches(0.5)
# #                 content_top = Inches(1.5)
# #                 content_width = Inches(5.0)
# #                 content_height = Inches(4.5)
                
# #                 content_box = content_slide.shapes.add_textbox(content_left, content_top, content_width, content_height)
                
# #                 text_frame = content_box.text_frame
# #                 text_frame.word_wrap = True
                
# #                 body_font = content_slide_styles.get('body_font', {})
                
# #                 for point in slide_data.get("points", []):
# #                     if text_frame.paragraphs and text_frame.paragraphs[0].text == "":
# #                         p = text_frame.paragraphs[0]
# #                     else:
# #                         p = text_frame.add_paragraph()
                    
# #                     p.text = "• " + point
                    
# #                     p.font.name = body_font.get('name', 'Calibri')
# #                     p.font.size = Pt(body_font.get('size', 18))
# #                     body_color = body_font.get('color', {'r': 50, 'g': 50, 'b': 50})
# #                     p.font.color.rgb = RGBColor(body_color['r'], body_color['g'], body_color['b'])
                    
# #                     p.space_before = Pt(6)
# #                     p.space_after = Pt(6)
# #                     p.alignment = {
# #                         'center': PP_ALIGN.CENTER,
# #                         'left': PP_ALIGN.LEFT,
# #                         'right': PP_ALIGN.RIGHT
# #                     }.get(body_font.get('alignment', 'left'), PP_ALIGN.LEFT)
                    
# #                     points_styling.append({
# #                         "text": point,
# #                         "level": 0,
# #                         "font_name": body_font.get('name', 'Calibri'),
# #                         "font_size": body_font.get('size', 18),
# #                         "color": body_color,
# #                         "alignment": body_font.get('alignment', 'left'),
# #                         "space_before": 6,
# #                         "space_after": 6
# #                     })
            
# #             content_image_style = {}
# #             if image_prompts and slide_index in image_prompts:
# #                 img_left = Inches(6.0)
# #                 img_top = Inches(1.5)
# #                 img_width = Inches(3.5)
# #                 img_height = Inches(4.5)
                
# #                 img_placeholder = content_slide.shapes.add_shape(
# #                     1, img_left, img_top, img_width, img_height
# #                 )
                
# #                 img_placeholder.fill.solid()
# #                 img_placeholder.fill.fore_color.rgb = RGBColor(245, 245, 245)
# #                 img_placeholder.line.color.rgb = RGBColor(200, 200, 200)
# #                 img_placeholder.line.width = Pt(1.5)
# #                 img_placeholder.line.dash_style = 2
                
# #                 text_frame = img_placeholder.text_frame
# #                 text_frame.word_wrap = True
# #                 text_frame.vertical_anchor = MSO_ANCHOR.MIDDLE
                
# #                 icon_p = text_frame.add_paragraph()
# #                 icon_p.text = "🖼️"
# #                 icon_p.alignment = PP_ALIGN.CENTER
# #                 icon_p.font.size = Pt(48)
# #                 icon_p.space_after = Pt(10)
                
# #                 prompt_p = text_frame.add_paragraph()
# #                 prompt_p.text = image_prompts[slide_index]
# #                 prompt_p.alignment = PP_ALIGN.CENTER
# #                 prompt_p.font.italic = True
# #                 prompt_p.font.size = Pt(14)
# #                 prompt_p.font.color.rgb = RGBColor(100, 100, 100)
                
# #                 content_image_style = {
# #                     "left": 6.0,
# #                     "top": 1.5,
# #                     "width": 3.5,
# #                     "height": 4.5,
# #                     "fill_color": {"r": 245, "g": 245, "b": 245},
# #                     "border_color": {"r": 200, "g": 200, "b": 200},
# #                     "border_width": 1.5,
# #                     "border_style": "dashed"
# #                 }
            
# #             preview_data["slides"].append({
# #                 "type": "content",
# #                 "title": slide_data.get("title", f"Slide {i+1}"),
# #                 "points": slide_data.get("points", []),
# #                 "points_styling": points_styling,
# #                 "has_image": slide_index in image_prompts if image_prompts else False,
# #                 "image_prompt": image_prompts.get(slide_index) if image_prompts else None,
# #                 "image_style": content_image_style
# #             })
        
# #         temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".pptx")
# #         prs.save(temp_file.name)
# #         temp_file.close()
        
# #         return temp_file.name, preview_data
    
# #     except Exception as e:
# #         logger.error(f"PowerPoint creation error: {str(e)}")
# #         raise Exception(f"Failed to create PowerPoint: {str(e)}")
# # @app.route('/generate_ppt', methods=['POST'])
# # def generate_ppt():
# #     try:
# #         # Get request data
# #         data = request.json
# #         topic = data.get('topic')
# #         num_slides = int(data.get('num_slides', 3))
# #         template = data.get('template', 'default')  # Get selected template
        
# #         # Validate inputs
# #         if not topic:
# #             return jsonify({"error": "Topic is required"}), 400
# #         if num_slides < 1 or num_slides > 20:
# #             return jsonify({"error": "Number of slides must be between 1 and 20"}), 400
        
# #         # Generate content
# #         logger.info(f"Generating content for topic: {topic} with {num_slides} slides")
# #         content_data = generate_text_content(topic, num_slides)
        
# #         # Generate image prompts for all slides
# #         image_prompts = {}
# #         try:
# #             # Generate title slide image prompt
# #             logger.info("Generating title image prompt")
# #             title_image_prompt = generate_image_prompt(topic)
# #             if title_image_prompt:
# #                 image_prompts["title"] = title_image_prompt
            
# #             # Generate image prompts for each content slide
# #             logger.info("Generating slide image prompts")
# #             for i, slide_data in enumerate(content_data.get("slides", [])):
# #                 slide_title = slide_data.get("title", "")
# #                 slide_image_prompt = generate_image_prompt(f"{topic} - {slide_title}")
# #                 if slide_image_prompt:
# #                     image_prompts[str(i)] = slide_image_prompt
                
# #         except Exception as e:
# #             logger.warning(f"Image prompt generation failed: {str(e)}")
        
# #         # Create PowerPoint with selected template
# #         logger.info(f"Creating PowerPoint presentation with template: {template}")
# #         ppt_file, preview_data = create_presentation(content_data, image_prompts, template)
        
# #         # Generate a unique filename for the user to download
# #         unique_id = uuid.uuid4().hex[:8]
# #         filename = f"{topic.replace(' ', '_')}_{unique_id}.pptx"
# #         user_filename = os.path.join("static", "downloads", filename)
        
# #         # Ensure directory exists
# #         os.makedirs(os.path.dirname(user_filename), exist_ok=True)
        
# #         # Copy the temporary file to the user-facing location
# #         with open(ppt_file, 'rb') as src, open(user_filename, 'wb') as dst:
# #             dst.write(src.read())
        
# #         # Clean up the temporary file
# #         os.unlink(ppt_file)
        
# #         # Return success response with content data for previewing/editing
# #         return jsonify({
# #             "success": True,
# #             "filename": filename,
# #             "download_url": f"/static/downloads/{filename}",
# #             "content": content_data,
# #             "image_prompts": image_prompts,
# #             "template": template,
# #             "preview_data": preview_data  # Include the preview data for accurate HTML rendering
# #         })
        
# #     except Exception as e:
# #         logger.error(f"Error processing request: {str(e)}")
# #         return jsonify({"error": str(e)}), 500

# # @app.route('/update_ppt', methods=['POST'])
# # def update_ppt():
# #     try:
# #         # Get updated content
# #         data = request.json
# #         content_data = data.get('content')
# #         image_prompts = data.get('image_prompts', {})
# #         template = data.get('template', 'default')
        
# #         # Validate inputs
# #         if not content_data or 'title' not in content_data or 'slides' not in content_data:
# #             return jsonify({"error": "Invalid presentation content"}), 400
        
# #         # Create updated PowerPoint
# #         logger.info("Creating updated PowerPoint presentation")
# #         ppt_file, preview_data = create_presentation(content_data, image_prompts, template)
        
# #         # Generate a unique filename for the user to download
# #         unique_id = uuid.uuid4().hex[:8]
# #         topic = content_data.get("title", "Presentation").replace(' ', '_')
# #         filename = f"{topic}_{unique_id}.pptx"
# #         user_filename = os.path.join("static", "downloads", filename)
        
# #         # Ensure directory exists
# #         os.makedirs(os.path.dirname(user_filename), exist_ok=True)
        
# #         # Copy the temporary file to the user-facing location
# #         with open(ppt_file, 'rb') as src, open(user_filename, 'wb') as dst:
# #             dst.write(src.read())
        
# #         # Clean up the temporary file
# #         os.unlink(ppt_file)
        
# #         return jsonify({
# #             "success": True,
# #             "filename": filename,
# #             "download_url": f"/static/downloads/{filename}",
# #             "preview_data": preview_data  # Include the preview data for accurate HTML rendering
# #         })
        
# #     except Exception as e:
# #         logger.error(f"Error updating presentation: {str(e)}")
# #         return jsonify({"error": str(e)}), 500


# # @app.route('/')
# # def index():
# #     return app.send_static_file('index.html')

# # # Serve static files (CSS, JS)
# # @app.route('/static/<path:path>')
# # def serve_static(path):
# #     return app.send_static_file(path)

# # @app.route('/get_templates', methods=['GET'])
# # def get_templates():
# #     """
# #     Retrieve available presentation templates
    
# #     :return: JSON response with template information
# #     """
# #     try:
# #         # Get all templates
# #         templates = template_manager.get_all_templates()
        
# #         # Prepare template response with minimal necessary details
# #         template_response = {}
# #         for key, template in templates.items():
# #             template_response[key] = {
# #                 "name": template.get('name', key),
# #                 "description": template.get('description', ''),
# #                 "preview_image": template.get('preview_image', ''),
# #                 "styles": template.get('styles', {})  # Include styles for accurate preview
# #             }
        
# #         return jsonify({
# #             "success": True,
# #             "templates": template_response
# #         })
# #     except Exception as e:
# #         logger.error(f"Error retrieving templates: {str(e)}")
# #         return jsonify({"error": "Failed to retrieve templates"}), 500


# # # Download endpoint
# # @app.route('/download/<filename>')
# # def download_file(filename):
# #     file_path = os.path.join("static", "downloads", filename)
# #     if not os.path.exists(file_path):
# #         return jsonify({"error": "File not found"}), 404
# #     return send_file(file_path, as_attachment=True)

# # if __name__ == '__main__':
# #     # Ensure download directory exists
# #     os.makedirs(os.path.join("static", "downloads"), exist_ok=True)
    
# #     # Run the app
# #     app.run(debug=True)




# from flask import Flask, request, jsonify, send_file, redirect, url_for, render_template, session
# from pptx import Presentation
# from pptx.util import Inches, Pt
# from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
# from pptx.dml.color import RGBColor
# import requests
# import os
# import json
# import tempfile
# import uuid
# import logging
# from template_manager import TemplateManager
# from werkzeug.security import generate_password_hash, check_password_hash
# import sqlite3
# from io import BytesIO
# from flask_cors import CORS

# app = Flask(__name__)
# CORS(app)
# template_manager = TemplateManager()

# logging.basicConfig(level=logging.INFO)
# logger = logging.getLogger(__name__)

# app.secret_key = 'your_secret_key'

# def get_db():
#     conn = sqlite3.connect('users.db')
#     conn.row_factory = sqlite3.Row
#     return conn

# @app.route('/register', methods=['GET', 'POST'])
# def register():
#     if request.method == 'POST':
#         username = request.form['username']
#         email = request.form['email']
#         password = request.form['password']
#         hashed_password = generate_password_hash(password)
#         try:
#             conn = get_db()
#             c = conn.cursor()
#             c.execute('INSERT INTO users (username, email, password) VALUES (?, ?, ?)',
#                       (username, email, hashed_password))
#             conn.commit()
#             conn.close()
#             return redirect(url_for('login'))
#         except sqlite3.IntegrityError:
#             conn.close()
#             return render_template('register.html', error='Username or email already exists')
#     return render_template('register.html')

# @app.route('/login', methods=['GET', 'POST'])
# def login():
#     if request.method == 'POST':
#         email = request.form['email']
#         password = request.form['password']
#         conn = get_db()
#         c = conn.cursor()
#         c.execute('SELECT * FROM users WHERE email = ?', (email,))
#         user = c.fetchone()
#         conn.close()
#         if user and check_password_hash(user['password'], password):
#             session['user_id'] = user['id']
#             session['username'] = user['username']
#             return redirect(url_for('index'))
#         else:
#             return render_template('login.html', error='Invalid email or password')
#     return render_template('login.html')

# @app.route('/logout')
# def logout():
#     session.pop('user_id', None)
#     session.pop('username', None)
#     return redirect(url_for('login'))

# def login_required(f):
#     def wrapper(*args, **kwargs):
#         if 'user_id' not in session:
#             return redirect(url_for('login'))
#         return f(*args, **kwargs)
#     wrapper.__name__ = f.__name__
#     return wrapper

# OLLAMA_ENDPOINT = "http://localhost:11434/api/generate"

# def generate_text_content(topic, num_slides):
#     try:
#         prompt = f"""Generate a detailed JSON for a presentation about '{topic}' with {num_slides} slides.
#         Each slide should have the following:
#         - A detailed title
#         - At least 5 concise and informative bullet points per slide (if applicable)
#         - Provide some additional explanations or insights for each bullet point
#         - Ensure the content is rich, professional, and informative
#         Format EXACTLY as this JSON structure:
#         {{
#             "title": "Overall Presentation Title",
#             "slides": [
#                 {{
#                     "title": "Slide 1 Title",
#                     "points": [
#                         "Point 1: Detailed explanation or context",
#                         "Point 2: Detailed explanation or context",
#                         "Point 3: Detailed explanation or context",
#                         "Point 4: Additional context or related points",
#                         "Point 5: Further insights or examples"
#                     ]
#                 }},
#                 ...
#             ]
#         }}
#         Requirements:
#         - Use clear, professional language
#         - Ensure each slide has a meaningful title
#         - Create at least 5 detailed, informative bullet points per slide
#         - Provide explanations, context, or examples where relevant
#         - Avoid any markdown, code blocks, or extra formatting
#         """
#         payload = {
#             "model": "llama3.2:1b",
#             "prompt": prompt,
#             "stream": False,
#             "format": "json"
#         }
#         response = requests.post(OLLAMA_ENDPOINT, json=payload)
#         if response.status_code != 200:
#             logger.error(f"Ollama API error: {response.status_code} - {response.text}")
#             raise Exception(f"Ollama API error: {response.status_code}")
#         content = response.json()["response"]
#         if "```json" in content:
#             content = content.split("```json")[1].split("```")[0].strip()
#         elif "```" in content:
#             content = content.split("```")[1].split("```")[0].strip()
#         presentation_data = json.loads(content)
#         if not isinstance(presentation_data, dict) or 'title' not in presentation_data or 'slides' not in presentation_data:
#             raise ValueError("Invalid JSON structure")
#         for slide in presentation_data.get('slides', []):
#             if 'title' not in slide or 'points' not in slide:
#                 raise ValueError("Invalid slide structure")
#         return presentation_data
#     except Exception as e:
#         logger.error(f"Text generation error: {str(e)}")
#         return {
#             "title": topic,
#             "slides": [
#                 {
#                     "title": f"Introduction to {topic}",
#                     "points": [
#                         "Overview of the topic with more context and background",
#                         "Key points to discuss with additional details",
#                         "Importance and relevance with examples or data"
#                     ]
#                 },
#                 {
#                     "title": "Main Concepts",
#                     "points": [
#                         "First main concept with detailed examples",
#                         "Second main concept with further elaboration",
#                         "Third main concept with supporting data or case studies"
#                     ]
#                 },
#                 {
#                     "title": "Conclusion",
#                     "points": [
#                         "Summary of key takeaways with insights",
#                         "Future implications with potential applications",
#                         "Call to action with a proposed next step or idea"
#                     ]
#                 }
#             ]
#         }

# def generate_image_prompt(prompt):
#     return f"Professional presentation image related to: {prompt}"

# def create_presentation(content_data, image_prompts=None, template="default"):
#     try:
#         template_config = template_manager.get_template(template) or template_manager.get_template('default')
#         styles = template_config.get('styles', {})
#         title_slide_styles = styles.get('title_slide', {})
#         content_slide_styles = styles.get('content_slide', {})
#         image_slide_styles = styles.get('image_slide', {})
        
#         preview_data = {
#             "title": content_data.get("title", "Presentation"),
#             "template": template,
#             "styles": {
#                 "title_slide": {
#                     "background": title_slide_styles.get('background', {'type': 'solid', 'color': {'r': 240, 'g': 240, 'b': 240}}),
#                     "title_font": title_slide_styles.get('title_font', {'name': 'Calibri', 'size': 44, 'color': {'r': 0, 'g': 0, 'b': 0}, 'bold': True, 'alignment': 'center'}),
#                     "image_position": title_slide_styles.get('image_position', {'left': 2.5, 'top': 4.0, 'width': 5.0, 'height': 2.5})
#                 },
#                 "content_slide": {
#                     "background": content_slide_styles.get('background', {'type': 'solid', 'color': {'r': 255, 'g': 255, 'b': 255}}),
#                     "title_font": content_slide_styles.get('title_font', {'name': 'Calibri', 'size': 32, 'color': {'r': 0, 'g': 0, 'b': 0}, 'bold': True, 'alignment': 'left'}),
#                     "body_font": content_slide_styles.get('body_font', {'name': 'Calibri', 'size': 18, 'color': {'r': 50, 'g': 50, 'b': 50}, 'alignment': 'left'}),
#                     "image_position": content_slide_styles.get('image_position', {'left': 6.0, 'top': 1.5, 'width': 3.5, 'height': 4.5})
#                 },
#                 "image_slide": {
#                     "fill_color": image_slide_styles.get('fill_color', {'r': 245, 'g': 245, 'b': 245}),
#                     "border_color": image_slide_styles.get('border_color', {'r': 200, 'g': 200, 'b': 200}),
#                     "border_width": image_slide_styles.get('border_width', 1.5),
#                     "border_style": image_slide_styles.get('border_style', 'dashed')
#                 }
#             },
#             "slides": []
#         }
        
#         prs = Presentation()
        
#         # Title Slide
#         blank_slide_layout = prs.slide_layouts[6]
#         title_slide = prs.slides.add_slide(blank_slide_layout)
        
#         background_settings = title_slide_styles.get('background', {})
#         background = title_slide.background
#         fill = background.fill
#         fill.solid()
#         if background_settings.get('type') == 'solid':
#             bg_color = background_settings.get('color', {'r': 240, 'g': 240, 'b': 240})
#         else:  # Gradient fallback to start color
#             bg_color = background_settings.get('gradient_start', {'r': 240, 'g': 240, 'b': 240})
#         fill.fore_color.rgb = RGBColor(bg_color['r'], bg_color['g'], bg_color['b'])
        
#         left = Inches(1.0)
#         top = Inches(2.0)
#         width = Inches(8.0)
#         height = Inches(1.5)
#         title_box = title_slide.shapes.add_textbox(left, top, width, height)
#         title_frame = title_box.text_frame
#         title_frame.text = content_data.get("title", "Presentation")
#         title_para = title_frame.paragraphs[0]
#         title_font_settings = title_slide_styles.get('title_font', {})
#         title_para.font.name = title_font_settings.get('name', 'Calibri')
#         title_para.font.size = Pt(title_font_settings.get('size', 44))
#         title_color = title_font_settings.get('color', {'r': 0, 'g': 0, 'b': 0})
#         title_para.font.color.rgb = RGBColor(title_color['r'], title_color['g'], title_color['b'])
#         title_para.font.bold = title_font_settings.get('bold', True)
#         title_para.alignment = PP_ALIGN.CENTER
        
#         title_image_style = {}
#         if image_prompts and "title" in image_prompts:
#             image_position = title_slide_styles.get('image_position', {'left': 2.5, 'top': 4.0, 'width': 5.0, 'height': 2.5})
#             img_left = Inches(image_position.get('left', 2.5))
#             img_top = Inches(image_position.get('top', 4.0))
#             img_width = Inches(image_position.get('width', 5.0))
#             img_height = Inches(image_position.get('height', 2.5))
#             img_placeholder = title_slide.shapes.add_shape(1, img_left, img_top, img_width, img_height)
#             img_placeholder.fill.solid()
#             fill_color = image_slide_styles.get('fill_color', {'r': 245, 'g': 245, 'b': 245})
#             img_placeholder.fill.fore_color.rgb = RGBColor(fill_color['r'], fill_color['g'], fill_color['b'])
#             border_color = image_slide_styles.get('border_color', {'r': 200, 'g': 200, 'b': 200})
#             img_placeholder.line.color.rgb = RGBColor(border_color['r'], border_color['g'], border_color['b'])
#             img_placeholder.line.width = Pt(image_slide_styles.get('border_width', 1.5))
#             img_placeholder.line.dash_style = 2 if image_slide_styles.get('border_style', 'dashed') == 'dashed' else 1
#             text_frame = img_placeholder.text_frame
#             text_frame.word_wrap = True
#             text_frame.vertical_anchor = MSO_ANCHOR.MIDDLE
#             icon_p = text_frame.add_paragraph()
#             icon_p.text = "🖼️"
#             icon_p.alignment = PP_ALIGN.CENTER
#             icon_p.font.size = Pt(48)
#             icon_p.space_after = Pt(10)
#             prompt_p = text_frame.add_paragraph()
#             prompt_p.text = image_prompts['title']
#             prompt_p.alignment = PP_ALIGN.CENTER
#             prompt_p.font.italic = True
#             prompt_p.font.size = Pt(14)
#             prompt_p.font.color.rgb = RGBColor(100, 100, 100)
#             title_image_style = {
#                 "left": image_position.get('left', 2.5),
#                 "top": image_position.get('top', 4.0),
#                 "width": image_position.get('width', 5.0),
#                 "height": image_position.get('height', 2.5),
#                 "fill_color": fill_color,
#                 "border_color": border_color,
#                 "border_width": image_slide_styles.get('border_width', 1.5),
#                 "border_style": image_slide_styles.get('border_style', 'dashed')
#             }
        
#         preview_data["slides"].append({
#             "type": "title",
#             "title": content_data.get("title", "Presentation"),
#             "has_image": "title" in image_prompts if image_prompts else False,
#             "image_prompt": image_prompts.get("title") if image_prompts else None,
#             "image_style": title_image_style
#         })
        
#         # Content Slides
#         for i, slide_data in enumerate(content_data.get("slides", [])):
#             slide_index = str(i)
#             content_slide = prs.slides.add_slide(blank_slide_layout)
#             background_settings = content_slide_styles.get('background', {})
#             background = content_slide.background
#             fill = background.fill
#             fill.solid()
#             if background_settings.get('type') == 'solid':
#                 bg_color = background_settings.get('color', {'r': 255, 'g': 255, 'b': 255})
#             else:  # Gradient fallback
#                 bg_color = background_settings.get('gradient_start', {'r': 255, 'g': 255, 'b': 255})
#             fill.fore_color.rgb = RGBColor(bg_color['r'], bg_color['g'], bg_color['b'])
            
#             title_left = Inches(0.5)
#             title_top = Inches(0.5)
#             title_width = Inches(9.0)
#             title_height = Inches(0.8)
#             title_box = content_slide.shapes.add_textbox(title_left, title_top, title_width, title_height)
#             title_frame = title_box.text_frame
#             title_frame.text = slide_data.get("title", f"Slide {i+1}")
#             title_para = title_frame.paragraphs[0]
#             title_font = content_slide_styles.get('title_font', {})
#             title_para.font.name = title_font.get('name', 'Calibri')
#             title_para.font.size = Pt(title_font.get('size', 32))
#             title_color = title_font.get('color', {'r': 0, 'g': 0, 'b': 0})
#             title_para.font.color.rgb = RGBColor(title_color['r'], title_color['g'], title_color['b'])
#             title_para.font.bold = title_font.get('bold', True)
#             title_para.alignment = {
#                 'center': PP_ALIGN.CENTER,
#                 'left': PP_ALIGN.LEFT,
#                 'right': PP_ALIGN.RIGHT
#             }.get(title_font.get('alignment', 'left'), PP_ALIGN.LEFT)
            
#             points_styling = []
#             if slide_data.get("points", []):
#                 content_left = Inches(0.5)
#                 content_top = Inches(1.5)
#                 content_width = Inches(5.0)
#                 content_height = Inches(4.5)
#                 content_box = content_slide.shapes.add_textbox(content_left, content_top, content_width, content_height)
#                 text_frame = content_box.text_frame
#                 text_frame.word_wrap = True
#                 body_font = content_slide_styles.get('body_font', {})
#                 for point in slide_data.get("points", []):
#                     if text_frame.paragraphs and text_frame.paragraphs[0].text == "":
#                         p = text_frame.paragraphs[0]
#                     else:
#                         p = text_frame.add_paragraph()
#                     p.text = "• " + point
#                     p.font.name = body_font.get('name', 'Calibri')
#                     p.font.size = Pt(body_font.get('size', 18))
#                     body_color = body_font.get('color', {'r': 50, 'g': 50, 'b': 50})
#                     p.font.color.rgb = RGBColor(body_color['r'], body_color['g'], body_color['b'])
#                     p.space_before = Pt(6)
#                     p.space_after = Pt(6)
#                     p.alignment = {
#                         'center': PP_ALIGN.CENTER,
#                         'left': PP_ALIGN.LEFT,
#                         'right': PP_ALIGN.RIGHT
#                     }.get(body_font.get('alignment', 'left'), PP_ALIGN.LEFT)
#                     points_styling.append({
#                         "text": point,
#                         "level": 0,
#                         "font_name": body_font.get('name', 'Calibri'),
#                         "font_size": body_font.get('size', 18),
#                         "color": body_color,
#                         "alignment": body_font.get('alignment', 'left'),
#                         "space_before": 6,
#                         "space_after": 6
#                     })
            
#             content_image_style = {}
#             if image_prompts and slide_index in image_prompts:
#                 image_position = content_slide_styles.get('image_position', {'left': 6.0, 'top': 1.5, 'width': 3.5, 'height': 4.5})
#                 img_left = Inches(image_position.get('left', 6.0))
#                 img_top = Inches(image_position.get('top', 1.5))
#                 img_width = Inches(image_position.get('width', 3.5))
#                 img_height = Inches(image_position.get('height', 4.5))
#                 img_placeholder = content_slide.shapes.add_shape(1, img_left, img_top, img_width, img_height)
#                 img_placeholder.fill.solid()
#                 fill_color = image_slide_styles.get('fill_color', {'r': 245, 'g': 245, 'b': 245})
#                 img_placeholder.fill.fore_color.rgb = RGBColor(fill_color['r'], fill_color['g'], fill_color['b'])
#                 border_color = image_slide_styles.get('border_color', {'r': 200, 'g': 200, 'b': 200})
#                 img_placeholder.line.color.rgb = RGBColor(border_color['r'], border_color['g'], border_color['b'])
#                 img_placeholder.line.width = Pt(image_slide_styles.get('border_width', 1.5))
#                 img_placeholder.line.dash_style = 2 if image_slide_styles.get('border_style', 'dashed') == 'dashed' else 1
#                 text_frame = img_placeholder.text_frame
#                 text_frame.word_wrap = True
#                 text_frame.vertical_anchor = MSO_ANCHOR.MIDDLE
#                 icon_p = text_frame.add_paragraph()
#                 icon_p.text = "🖼️"
#                 icon_p.alignment = PP_ALIGN.CENTER
#                 icon_p.font.size = Pt(48)
#                 icon_p.space_after = Pt(10)
#                 prompt_p = text_frame.add_paragraph()
#                 prompt_p.text = image_prompts[slide_index]
#                 prompt_p.alignment = PP_ALIGN.CENTER
#                 prompt_p.font.italic = True
#                 prompt_p.font.size = Pt(14)
#                 prompt_p.font.color.rgb = RGBColor(100, 100, 100)
#                 content_image_style = {
#                     "left": image_position.get('left', 6.0),
#                     "top": image_position.get('top', 1.5),
#                     "width": image_position.get('width', 3.5),
#                     "height": image_position.get('height', 4.5),
#                     "fill_color": fill_color,
#                     "border_color": border_color,
#                     "border_width": image_slide_styles.get('border_width', 1.5),
#                     "border_style": image_slide_styles.get('border_style', 'dashed')
#                 }
            
#             preview_data["slides"].append({
#                 "type": "content",
#                 "title": slide_data.get("title", f"Slide {i+1}"),
#                 "points": slide_data.get("points", []),
#                 "points_styling": points_styling,
#                 "has_image": slide_index in image_prompts if image_prompts else False,
#                 "image_prompt": image_prompts.get(slide_index) if image_prompts else None,
#                 "image_style": content_image_style
#             })
        
#         temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".pptx")
#         prs.save(temp_file.name)
#         temp_file.close()
#         return temp_file.name, preview_data
    
#     except Exception as e:
#         logger.error(f"PowerPoint creation error: {str(e)}")
#         raise Exception(f"Failed to create PowerPoint: {str(e)}")

# @app.route('/generate_ppt', methods=['POST'])
# def generate_ppt():
#     try:
#         data = request.json
#         topic = data.get('topic')
#         num_slides = int(data.get('num_slides', 3))
#         template = data.get('template', 'default')
#         if not topic:
#             return jsonify({"error": "Topic is required"}), 400
#         if num_slides < 1 or num_slides > 20:
#             return jsonify({"error": "Number of slides must be between 1 and 20"}), 400
#         logger.info(f"Generating content for topic: {topic} with {num_slides} slides")
#         content_data = generate_text_content(topic, num_slides)
#         image_prompts = {}
#         try:
#             logger.info("Generating title image prompt")
#             title_image_prompt = generate_image_prompt(topic)
#             if title_image_prompt:
#                 image_prompts["title"] = title_image_prompt
#             logger.info("Generating slide image prompts")
#             for i, slide_data in enumerate(content_data.get("slides", [])):
#                 slide_title = slide_data.get("title", "")
#                 slide_image_prompt = generate_image_prompt(f"{topic} - {slide_title}")
#                 if slide_image_prompt:
#                     image_prompts[str(i)] = slide_image_prompt
#         except Exception as e:
#             logger.warning(f"Image prompt generation failed: {str(e)}")
#         logger.info(f"Creating PowerPoint presentation with template: {template}")
#         ppt_file, preview_data = create_presentation(content_data, image_prompts, template)
#         unique_id = uuid.uuid4().hex[:8]
#         filename = f"{topic.replace(' ', '_')}_{unique_id}.pptx"
#         user_filename = os.path.join("static", "downloads", filename)
#         os.makedirs(os.path.dirname(user_filename), exist_ok=True)
#         with open(ppt_file, 'rb') as src, open(user_filename, 'wb') as dst:
#             dst.write(src.read())
#         os.unlink(ppt_file)
#         return jsonify({
#             "success": True,
#             "filename": filename,
#             "download_url": f"/static/downloads/{filename}",
#             "content": content_data,
#             "image_prompts": image_prompts,
#             "template": template,
#             "preview_data": preview_data
#         })
#     except Exception as e:
#         logger.error(f"Error processing request: {str(e)}")
#         return jsonify({"error": str(e)}), 500

# @app.route('/update_ppt', methods=['POST'])
# def update_ppt():
#     try:
#         data = request.json
#         content_data = data.get('content')
#         image_prompts = data.get('image_prompts', {})
#         template = data.get('template', 'default')
#         if not content_data or 'title' not in content_data or 'slides' not in content_data:
#             return jsonify({"error": "Invalid presentation content"}), 400
#         logger.info("Creating updated PowerPoint presentation")
#         ppt_file, preview_data = create_presentation(content_data, image_prompts, template)
#         unique_id = uuid.uuid4().hex[:8]
#         topic = content_data.get("title", "Presentation").replace(' ', '_')
#         filename = f"{topic}_{unique_id}.pptx"
#         user_filename = os.path.join("static", "downloads", filename)
#         os.makedirs(os.path.dirname(user_filename), exist_ok=True)
#         with open(ppt_file, 'rb') as src, open(user_filename, 'wb') as dst:
#             dst.write(src.read())
#         os.unlink(ppt_file)
#         return jsonify({
#             "success": True,
#             "filename": filename,
#             "download_url": f"/static/downloads/{filename}",
#             "preview_data": preview_data
#         })
#     except Exception as e:
#         logger.error(f"Error updating presentation: {str(e)}")
#         return jsonify({"error": str(e)}), 500

# @app.route('/')
# def index():
#     return app.send_static_file('index.html')

# @app.route('/static/<path:path>')
# def serve_static(path):
#     return app.send_static_file(path)

# @app.route('/get_templates', methods=['GET'])
# def get_templates():
#     try:
#         templates = template_manager.get_all_templates()
#         template_response = {}
#         for key, template in templates.items():
#             template_response[key] = {
#                 "name": template.get('name', key),
#                 "description": template.get('description', ''),
#                 "preview_image": template.get('preview_image', ''),
#                 "styles": template.get('styles', {})
#             }
#         return jsonify({
#             "success": True,
#             "templates": template_response
#         })
#     except Exception as e:
#         logger.error(f"Error retrieving templates: {str(e)}")
#         return jsonify({"error": "Failed to retrieve templates"}), 500

# @app.route('/download/<filename>')
# def download_file(filename):
#     file_path = os.path.join("static", "downloads", filename)
#     if not os.path.exists(file_path):
#         return jsonify({"error": "File not found"}), 404
#     return send_file(file_path, as_attachment=True)

# if __name__ == '__main__':
#     os.makedirs(os.path.join("static", "downloads"), exist_ok=True)
#     app.run(debug=True)