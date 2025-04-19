import os
import json
import logging

# Configure logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

class TemplateManager:
    def __init__(self, templates_dir='static/templates'):
        self.templates_dir = templates_dir
        self.templates = {}
        self.load_templates()

    def load_templates(self):
        try:
            if not os.path.exists(self.templates_dir):
                logging.error(f"Templates directory not found: {self.templates_dir}")
                return

            for filename in os.listdir(self.templates_dir):
                if filename.endswith('.json'):
                    filepath = os.path.join(self.templates_dir, filename)
                    try:
                        with open(filepath, 'r') as file:
                            template_data = json.load(file)
                        template_key = os.path.splitext(filename)[0]
                        self.templates[template_key] = template_data
                        logging.info(f"Loaded template: {template_key}")
                    except json.JSONDecodeError as e:
                        logging.error(f"Error decoding {filename}: {str(e)}")
                    except Exception as e:
                        logging.error(f"Error loading {filename}: {str(e)}")

            logging.info(f"Total templates loaded: {len(self.templates)}")
        except Exception as e:
            logging.error(f"Error in load_templates: {str(e)}")

    def get_template(self, template_name):
        return self.templates.get(template_name)

    def get_all_templates(self):
        return self.templates
    
    def validate_template(self, template_name):
        template = self.get_template(template_name)
        if not template:
            logging.error(f"Template {template_name} not found")
            return False
        
        required_keys = ['name', 'description', 'preview_image', 'styles']
        if not all(key in template for key in required_keys):
            logging.error(f"Template {template_name} missing required keys: {required_keys}")
            return False
        
        # Validate preview image
        preview_image = template.get('preview_image', '')
        if preview_image:
            preview_image_path = os.path.join('static', preview_image)
            if preview_image and not os.path.exists(preview_image_path):
                logging.error(f"Template {template_name} has invalid preview_image path: {preview_image_path}")
                return False
            else:
                logging.debug(f"Template {template_name} preview_image validated: {preview_image_path}")
        
        required_styles = ['title_slide', 'content_slide']
        styles = template.get('styles', {})
        if not all(style in styles for style in required_styles):
            logging.error(f"Template {template_name} missing required styles: {required_styles}")
            return False
        
        # Validate title slide
        title_slide = styles.get('title_slide', {})
        bg_settings = title_slide.get('background', {})
        title_font = title_slide.get('title_font', {})
        
        # Validate background
        if bg_settings.get('type') == 'solid':
            bg_color = bg_settings.get('color', {'r': 240, 'g': 240, 'b': 240})
            if not all(k in bg_color for k in ['r', 'g', 'b']):
                logging.error(f"Template {template_name} has invalid background color format")
                return False
        elif bg_settings.get('type') == 'gradient':
            gradient_start = bg_settings.get('gradient_start', {'r': 240, 'g': 240, 'b': 240})
            gradient_end = bg_settings.get('gradient_end', {'r': 200, 'g': 200, 'b': 200})
            if not all(k in gradient_start for k in ['r', 'g', 'b']) or not all(k in gradient_end for k in ['r', 'g', 'b']):
                logging.error(f"Template {template_name} has invalid gradient color format")
                return False
        
        # Validate background image
        for slide_type in ['title_slide', 'content_slide']:
            slide = styles.get(slide_type, {})
            bg_image = slide.get('background_image')
            if bg_image:
                image_path = os.path.join('static', bg_image)
                if not os.path.exists(image_path):
                    logging.error(f"Template {template_name} has invalid background_image path for {slide_type}: {image_path}")
                    return False
                else:
                    logging.debug(f"Template {template_name} background_image validated for {slide_type}: {image_path}")
        
        # Validate title font color
        title_color = title_font.get('color', {'r': 0, 'g': 0, 'b': 0})
        if not all(k in title_color for k in ['r', 'g', 'b']):
            logging.error(f"Template {template_name} has invalid title font color format")
            return False
        
        # Check for low contrast (only for solid backgrounds without images)
        if bg_settings.get('type') == 'solid' and not title_slide.get('background_image'):
            bg_color = bg_settings.get('color', {'r': 240, 'g': 240, 'b': 240})
            if (bg_color['r'] >= 200 and bg_color['g'] >= 200 and bg_color['b'] >= 200 and
                title_color['r'] >= 200 and title_color['g'] >= 200 and title_color['b'] >= 200):
                logging.warning(f"Template {template_name} has low contrast colors in title slide")
                return False
        
        # Validate image position
        for slide_type in ['title_slide', 'content_slide']:
            slide = styles.get(slide_type, {})
            image_position = slide.get('image_position', {})
            required_position_keys = ['left', 'top', 'width', 'height']
            if image_position and not all(k in image_position for k in required_position_keys):
                logging.error(f"Template {template_name} has invalid image_position in {slide_type}")
                return False
        
        # Validate image_slide properties
        image_slide = styles.get('image_slide', {})
        for key in ['fill_color', 'border_color']:
            if key in image_slide and not all(k in image_slide[key] for k in ['r', 'g', 'b']):
                logging.error(f"Template {template_name} has invalid {key} format in image_slide")
                return False
        
        logging.info(f"Template {template_name} validated successfully")
        return True