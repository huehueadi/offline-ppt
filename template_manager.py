# import os
# import json
# import logging

# class TemplateManager:
#     def __init__(self, templates_dir='static/templates'):
#         """
#         Initialize TemplateManager with the templates directory
        
#         :param templates_dir: Path to the directory containing template JSON files
#         """
#         self.templates_dir = templates_dir
#         self.templates = {}
#         self.load_templates()

#     def load_templates(self):
#         """
#         Load all template configurations from JSON files
#         """
#         try:
#             # Ensure the templates directory exists
#             if not os.path.exists(self.templates_dir):
#                 logging.warning(f"Templates directory not found: {self.templates_dir}")
#                 return

#             # Iterate through JSON files in the templates directory
#             for filename in os.listdir(self.templates_dir):
#                 if filename.endswith('.json'):
#                     filepath = os.path.join(self.templates_dir, filename)
#                     try:
#                         with open(filepath, 'r') as file:
#                             template_data = json.load(file)
                            
#                         # Use filename (without .json) as the key
#                         template_key = os.path.splitext(filename)[0]
#                         self.templates[template_key] = template_data
#                     except json.JSONDecodeError:
#                         logging.error(f"Error decoding template file: {filename}")
#                     except Exception as e:
#                         logging.error(f"Error loading template {filename}: {str(e)}")

#             logging.info(f"Loaded {len(self.templates)} templates")
#         except Exception as e:
#             logging.error(f"Error in load_templates: {str(e)}")

#     def get_template(self, template_name):
#         """
#         Retrieve a specific template configuration
        
#         :param template_name: Name of the template
#         :return: Template configuration or None
#         """
#         return self.templates.get(template_name)

#     def get_all_templates(self):
#         """
#         Get all available templates
        
#         :return: Dictionary of all templates
#         """
#         return self.templates

# def validate_template(self, template_name):
#     template = self.get_template(template_name)
#     if not template:
#         return False
#     required_keys = ['name', 'description', 'preview_image', 'styles']
#     if not all(key in template for key in required_keys):
#         return False
#     required_styles = ['title_slide', 'content_slide']
#     styles = template.get('styles', {})
#     if not all(style in styles for style in required_styles):
#         return False
#     for style in styles.values():
#         if 'background' not in style or 'title_font' not in style:
#             return False
#     return True
# # Optional: Create a global instance if needed
# template_manager = TemplateManager()



import os
import json
import logging

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
            logging.error(f"Template {template_name} missing required keys")
            return False
        return True

template_manager = TemplateManager()