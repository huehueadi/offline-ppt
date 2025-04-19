document.addEventListener('DOMContentLoaded', function() {
    // DOM Elements - Template Selection
    const templateSelectionSection = document.getElementById('template-selection');
    const templatesGrid = document.getElementById('templates-grid');
    const continueToContentBtn = document.getElementById('continue-to-content');
    const contentFormSection = document.getElementById('content-form');
    const selectedTemplateName = document.getElementById('selected-template-name');
    const selectedTemplatePreview = document.getElementById('selected-template-preview');
    const backToTemplatesBtn = document.getElementById('back-to-templates');
    
    // DOM Elements - Form and Actions
    const form = document.getElementById('ppt-form');
    const generateBtn = document.getElementById('generate-btn');
    const loadingSection = document.getElementById('loading');
    const previewSection = document.getElementById('preview-section');
    const previewContent = document.getElementById('preview-content');
    const editorSection = document.getElementById('editor-section');
    const resultSection = document.getElementById('result');
    const downloadLink = document.getElementById('download-link');
    const errorSection = document.getElementById('error');
    const errorMessage = document.getElementById('error-message');
    const tryAgainBtn = document.getElementById('try-again-btn');
    const statusMessage = document.querySelector('.status-message');
    
    // Action buttons
    const downloadBtn = document.getElementById('download-btn');
    const editBtn = document.getElementById('edit-btn');
    const presentationPreviewBtn = document.getElementById('presentation-preview-btn');
    const saveChangesBtn = document.getElementById('save-changes-btn');
    const cancelEditBtn = document.getElementById('cancel-edit-btn');
    
    // Store presentation data and selected template
    let presentationData = null;
    let selectedTemplate = null;
    
    // Status update messages
    const statusMessages = [
        "Connecting to local Ollama service...",
        "Generating presentation content...",
        "Creating slide content...",
        "Generating image prompts for slides...",
        "Building PowerPoint presentation with selected template...",
        "Finalizing your presentation..."
    ];
    let currentStatusIndex = 0;
    let statusInterval;

    // Load templates when the page loads
    loadTemplates();
    
    // Template selection handlers
    continueToContentBtn.addEventListener('click', function() {
        if (!selectedTemplate) {
            alert('Please select a template before continuing');
            return;
        }
        
        // Hide template selection and show content form
        templateSelectionSection.classList.add('hidden');
        contentFormSection.classList.remove('hidden');
    });
    
    backToTemplatesBtn.addEventListener('click', function() {
        // Hide content form and show template selection
        contentFormSection.classList.add('hidden');
        templateSelectionSection.classList.remove('hidden');
    });
    
    // Form submission
    form.addEventListener('submit', async function(e) {
        e.preventDefault();
        
        // Get form data
        const topic = document.getElementById('topic').value.trim();
        const numSlides = parseInt(document.getElementById('num_slides').value, 10);
        
        // Validate form data
        if (!topic) {
            showError('Please enter a presentation topic');
            return;
        }
        
        if (isNaN(numSlides) || numSlides < 1 || numSlides > 20) {
            showError('Number of slides must be between 1 and 20');
            return;
        }
        
        if (!selectedTemplate) {
            showError('Please select a template');
            return;
        }
        
        // Hide form and show loading indicator
        contentFormSection.classList.add('hidden');
        loadingSection.classList.remove('hidden');
        
        // Disable the generate button
        generateBtn.disabled = true;
        
        // Start status update cycle
        currentStatusIndex = 0;
        updateStatus(statusMessages[currentStatusIndex]);
        statusInterval = setInterval(cycleStatusMessages, 3000);
        
        try {
            // Send request to backend
            const response = await fetch('/generate_ppt', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    topic: topic,
                    num_slides: numSlides,
                    template: selectedTemplate.id
                })
            });
            
            // Clear status interval
            clearInterval(statusInterval);
            
            // Check response
            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.error || 'Failed to generate presentation');
            }
            
            // Parse response
            const data = await response.json();
            
            // Store presentation data
            presentationData = {
                content: data.content,
                image_prompts: data.image_prompts,
                template: data.template,
                preview_data: data.preview_data,
                download_url: data.download_url,
                filename: data.filename
            };
            
            // Update status
            updateStatus('Presentation ready!');
            
            // Generate HTML preview that matches the PowerPoint styling
            generateHtmlPreview(presentationData.preview_data);
            
            // Set download link
            downloadLink.href = data.download_url;
            downloadLink.setAttribute('download', data.filename);
            
            // Show preview section
            loadingSection.classList.add('hidden');
            previewSection.classList.remove('hidden');
            
        } catch (error) {
            clearInterval(statusInterval);
            console.error('Error:', error);
            showError(error.message || 'An unexpected error occurred');
        } finally {
            generateBtn.disabled = false;
        }
    });
    
    // Generate HTML preview that matches PowerPoint styling
// Generate HTML preview that matches PowerPoint styling
function generateHtmlPreview(previewData) {
    previewContent.innerHTML = '';
    
    if (!previewData || !previewData.slides || previewData.slides.length === 0) {
        previewContent.innerHTML = '<p>No preview data available</p>';
        return;
    }
    
    // Extract title and template styles with fallbacks
    const pptTitle = previewData.title || 'Presentation';
    const titleSlideStyles = previewData.styles?.title_slide || {};
    const contentSlideStyles = previewData.styles?.content_slide || {};
    
    // Create preview section title
    const previewTitle = document.createElement('h3');
    previewTitle.className = 'preview-title';
    previewTitle.textContent = pptTitle;
    previewContent.appendChild(previewTitle);
    
    // Create slides preview
    previewData.slides.forEach((slide, index) => {
        const slidePreview = document.createElement('div');
        slidePreview.className = 'slide-preview';
        
        // Apply slide styling based on type
        const isTitle = slide.type === 'title';
        const slideStyles = isTitle ? titleSlideStyles : contentSlideStyles;
        
        // Apply background color with fallback
        const bgColor = isTitle ? 
            (slide.background_color || {r: 240, g: 240, b: 240}) : 
            (slideStyles.background?.color || {r: 255, g: 255, b: 255});
        slidePreview.style.backgroundColor = `rgb(${bgColor.r}, ${bgColor.g}, ${bgColor.b})`;
        
        // Add slide title with consistent styling and positioning
        const slideTitle = document.createElement('h4');
        const titleFont = slideStyles.title_font || {};
        slideTitle.textContent = slide.title || `Slide ${index + 1}`;
        
        // Apply title font styling to match PowerPoint
        slideTitle.style.position = 'absolute';
        slideTitle.style.left = isTitle ? '80px' : '40px'; // 1 inch = 80px, 0.5 inch = 40px
        slideTitle.style.top = isTitle ? '160px' : '40px'; // 2 inch = 160px, 0.5 inch = 40px
        slideTitle.style.width = isTitle ? '640px' : '720px'; // 8 inch = 640px, 9 inch = 720px
        if (titleFont.name) slideTitle.style.fontFamily = titleFont.name;
        if (titleFont.size) slideTitle.style.fontSize = `${titleFont.size}px`;
        if (titleFont.bold) slideTitle.style.fontWeight = 'bold';
        const titleColor = isTitle ? 
            (slide.title_color || {r: 0, g: 0, b: 0}) : 
            (titleFont.color || {r: 0, g: 0, b: 0});
        slideTitle.style.color = `rgb(${titleColor.r}, ${titleColor.g}, ${titleColor.b})`;
        slideTitle.style.textAlign = titleFont.alignment || (isTitle ? 'center' : 'left');
        
        slidePreview.appendChild(slideTitle);
        
        // Add bullet points for content slides with consistent styling
        if (!isTitle && slide.points && slide.points.length > 0) {
            const pointsList = document.createElement('ul');
            pointsList.style.position = 'absolute';
            pointsList.style.left = '40px'; // 0.5 inch
            pointsList.style.top = '120px'; // 1.5 inch
            pointsList.style.width = '400px'; // 5 inch
            pointsList.style.paddingLeft = '20px'; // Match PowerPoint bullet indentation
            
            slide.points.forEach((point, pointIndex) => {
                const pointItem = document.createElement('li');
                pointItem.textContent = point;
                
                // Apply styling to match PowerPoint exactly
                if (slide.points_styling && slide.points_styling[pointIndex]) {
                    const styling = slide.points_styling[pointIndex];
                    if (styling.font_name) pointItem.style.fontFamily = styling.font_name;
                    if (styling.font_size) pointItem.style.fontSize = `${styling.font_size}px`;
                    pointItem.style.color = `rgb(${styling.color?.r || 50}, ${styling.color?.g || 50}, ${styling.color?.b || 50})`;
                    pointItem.style.textAlign = styling.alignment || 'left';
                    pointItem.style.marginBottom = `${styling.space_after || 6}px`;
                    pointItem.style.marginTop = `${styling.space_before || 6}px`;
                }
                
                pointsList.appendChild(pointItem);
            });
            
            slidePreview.appendChild(pointsList);
        }
        
        // Add image placeholder with consistent styling and positioning
        if (slide.has_image && slide.image_prompt && slide.image_style) {
            const imagePlaceholder = document.createElement('div');
            imagePlaceholder.className = 'image-placeholder';
            
            // Position and size to match PowerPoint (1 inch = 80px)
            imagePlaceholder.style.position = 'absolute';
            imagePlaceholder.style.left = `${slide.image_style.left * 80}px`;
            imagePlaceholder.style.top = `${slide.image_style.top * 80}px`;
            imagePlaceholder.style.width = `${slide.image_style.width * 80}px`;
            imagePlaceholder.style.height = `${slide.image_style.height * 80}px`;
            
            // Apply styling to match PowerPoint
            imagePlaceholder.style.backgroundColor = `rgb(${slide.image_style.fill_color?.r || 245}, ${slide.image_style.fill_color?.g || 245}, ${slide.image_style.fill_color?.b || 245})`;
            imagePlaceholder.style.border = `${slide.image_style.border_width || 1.5}px ${slide.image_style.border_style || 'dashed'} rgb(${slide.image_style.border_color?.r || 200}, ${slide.image_style.border_color?.g || 200}, ${slide.image_style.border_color?.b || 200})`;
            
            // Add icon and text
            const imageIcon = document.createElement('div');
            imageIcon.className = 'image-placeholder-icon';
            imageIcon.innerHTML = '🖼️';
            imageIcon.style.fontSize = '48px';
            imageIcon.style.marginBottom = '10px';
            imagePlaceholder.appendChild(imageIcon);
            
            const imageText = document.createElement('p');
            imageText.textContent = slide.image_prompt;
            imageText.style.margin = '0';
            imageText.style.fontStyle = 'italic';
            imageText.style.fontSize = '14px';
            imageText.style.color = '#646464';
            imagePlaceholder.appendChild(imageText);
            
            slidePreview.appendChild(imagePlaceholder);
        }
        
        previewContent.appendChild(slidePreview);
    });
}

// Open a full-screen PowerPoint-like preview
function openFullScreenPreview() {
    if (!presentationData || !presentationData.preview_data) {
        showError('Preview data not available');
        return;
    }
    
    const previewData = presentationData.preview_data;
    
    // Create a full-screen modal for presentation preview
    const modal = document.createElement('div');
    modal.className = 'presentation-modal';
    
    // Get styles for slides with fallbacks
    const titleSlideStyles = previewData.styles?.title_slide || {};
    const contentSlideStyles = previewData.styles?.content_slide || {};
    
    // Create modal content
    modal.innerHTML = `
        <div class="presentation-container">
            <div class="presentation-toolbar">
                <button class="close-btn">×</button>
                <div class="slide-counter">1 / ${previewData.slides.length}</div>
                <div class="presentation-controls">
                    <button class="prev-btn">◀</button>
                    <button class="next-btn">▶</button>
                </div>
            </div>
            
            <div class="presentation-content">
                ${previewData.slides.map((slide, index) => {
                    const isTitle = slide.type === 'title';
                    const slideStyles = isTitle ? titleSlideStyles : contentSlideStyles;
                    const bgColor = isTitle ? 
                        (slide.background_color || {r: 240, g: 240, b: 240}) : 
                        (slideStyles.background?.color || {r: 255, g: 255, b: 255});
                    const titleFont = slideStyles.title_font || {};
                    const titleColor = isTitle ? 
                        (slide.title_color || {r: 0, g: 0, b: 0}) : 
                        (titleFont.color || {r: 0, g: 0, b: 0});
                    
                    
                    
                    return `
                        <div class="presentation-slide ${index === 0 ? 'active' : ''}" style="background-color: rgb(${bgColor.r}, ${bgColor.g}, ${bgColor.b})">
                            <div class="slide-inner ${isTitle ? 'title-slide' : 'content-slide'}">
                                <h2 style="
                                    position: absolute;
                                    left: ${isTitle ? '80px' : '40px'};
                                    top: ${isTitle ? '160px' : '40px'};
                                    width: ${isTitle ? '640px' : '720px'};
                                    color: rgb(${titleColor.r}, ${titleColor.g}, ${titleColor.b});
                                    font-family: ${titleFont.name || 'inherit'};
                                    font-size: ${titleFont.size || 44}px;
                                    font-weight: ${titleFont.bold ? 'bold' : 'normal'};
                                    text-align: ${titleFont.alignment || (isTitle ? 'center' : 'left')};
                                ">
                                    ${slide.title || `Slide ${index + 1}`}
                                </h2>
                                
                                ${isTitle ? renderTitleSlideContent(slide) : renderContentSlideContent(slide)}
                            </div>
                        </div>
                    `;
                }).join('')}
            </div>
        </div>
    `;
    
    // Helper function to render title slide content
    function renderTitleSlideContent(slide) {
        if (slide.has_image && slide.image_prompt && slide.image_style) {
            return `
                <div class="image-placeholder" style="
                    position: absolute;
                    left: ${slide.image_style.left * 80}px;
                    top: ${slide.image_style.top * 80}px;
                    width: ${slide.image_style.width * 80}px;
                    height: ${slide.image_style.height * 80}px;
                    background-color: rgb(${slide.image_style.fill_color?.r || 245}, ${slide.image_style.fill_color?.g || 245}, ${slide.image_style.fill_color?.b || 245});
                    border: ${slide.image_style.border_width || 1.5}px ${slide.image_style.border_style || 'dashed'} rgb(${slide.image_style.border_color?.r || 200}, ${slide.image_style.border_color?.g || 200}, ${slide.image_style.border_color?.b || 200});
                ">
                    <div class="image-placeholder-icon" style="font-size: 48px; margin-bottom: 10px;">🖼️</div>
                    <p style="margin: 0; font-style: italic; font-size: 14px; color: #646464;">${slide.image_prompt}</p>
                </div>
            `;
        }
        return '';
    }
    
    // Helper function to render content slide content
    function renderContentSlideContent(slide) {
        let pointsHtml = '';
        if (slide.points && slide.points.length > 0) {
            pointsHtml = `
                <ul class="slide-points" style="
                    position: absolute;
                    left: 40px;
                    top: 120px;
                    width: 400px;
                    padding-left: 20px;
                ">
                    ${slide.points.map((point, i) => {
                        const styling = slide.points_styling && slide.points_styling[i] ? slide.points_styling[i] : {};
                        const color = styling.color || {r: 50, g: 50, b: 50};
                        return `
                            <li style="
                                font-family: ${styling.font_name || 'inherit'};
                                font-size: ${styling.font_size || 18}px;
                                color: rgb(${color.r}, ${color.g}, ${color.b});
                                text-align: ${styling.alignment || 'left'};
                                margin-bottom: ${styling.space_after || 6}px;
                                margin-top: ${styling.space_before || 6}px;
                            ">
                                ${point}
                            </li>
                        `;
                    }).join('')}
                </ul>
            `;
        }
        
        let imageHtml = '';
        if (slide.has_image && slide.image_prompt && slide.image_style) {
            imageHtml = `
                <div class="image-placeholder" style="
                    position: absolute;
                    left: ${slide.image_style.left * 80}px;
                    top: ${slide.image_style.top * 80}px;
                    width: ${slide.image_style.width * 80}px;
                    height: ${slide.image_style.height * 80}px;
                    background-color: rgb(${slide.image_style.fill_color?.r || 245}, ${slide.image_style.fill_color?.g || 245}, ${slide.image_style.fill_color?.b || 245});
                    border: ${slide.image_style.border_width || 1.5}px ${slide.image_style.border_style || 'dashed'} rgb(${slide.image_style.border_color?.r || 200}, ${slide.image_style.border_color?.g || 200}, ${slide.image_style.border_color?.b || 200});
                ">
                    <div class="image-placeholder-icon" style="font-size: 48px; margin-bottom: 10px;">🖼️</div>
                    <p style="margin: 0; font-style: italic; font-size: 14px; color: #646464;">${slide.image_prompt}</p>
                </div>
            `;
        }
        
        return pointsHtml + imageHtml;
    }
    
    // Add modal to the document
    document.body.appendChild(modal);
    
    // Modal controls
    const closeBtn = modal.querySelector('.close-btn');
    const prevBtn = modal.querySelector('.prev-btn');
    const nextBtn = modal.querySelector('.next-btn');
    const slides = modal.querySelectorAll('.presentation-slide');
    const slideCounter = modal.querySelector('.slide-counter');
    let currentSlide = 0;
    
    // Close modal
    closeBtn.addEventListener('click', () => {
        document.body.removeChild(modal);
    });
    
    // Navigate to previous slide
    prevBtn.addEventListener('click', () => {
        slides[currentSlide].classList.remove('active');
        currentSlide = (currentSlide - 1 + slides.length) % slides.length;
        slides[currentSlide].classList.add('active');
        slideCounter.textContent = `${currentSlide + 1} / ${slides.length}`;
    });
    
    // Navigate to next slide
    nextBtn.addEventListener('click', () => {
        slides[currentSlide].classList.remove('active');
        currentSlide = (currentSlide + 1) % slides.length;
        slides[currentSlide].classList.add('active');
        slideCounter.textContent = `${currentSlide + 1} / ${slides.length}`;
    });
    
    // Keyboard navigation
    document.addEventListener('keydown', function handleKeyPress(e) {
        if (e.key === 'Escape') {
            document.body.removeChild(modal);
            document.removeEventListener('keydown', handleKeyPress);
        } else if (e.key === 'ArrowLeft') {
            prevBtn.click();
        } else if (e.key === 'ArrowRight') {
            nextBtn.click();
        }
    });
}
    
    // Load templates from server
    async function loadTemplates() {
        try {
            // Show loading indicator in templates grid
            templatesGrid.innerHTML = `
                <div class="template-loading">
                    <div class="spinner"></div>
                    <p>Loading templates...</p>
                </div>
            `;
            
            const response = await fetch('/get_templates');
            if (!response.ok) {
                throw new Error('Failed to load templates');
            }
            
            const data = await response.json();
            
            // Clear loading indicator
            templatesGrid.innerHTML = '';
            
            // Check if we have templates
            if (Object.keys(data.templates).length === 0) {
                templatesGrid.innerHTML = `
                    <div class="no-templates">
                        <p>No templates available. Please check your template directory.</p>
                    </div>
                `;
                return;
            }
            
            // Create template cards
            Object.entries(data.templates).forEach(([key, template]) => {
                const templateCard = document.createElement('div');
                templateCard.className = 'template-card';
                templateCard.dataset.templateId = key;
                templateCard.dataset.templateInfo = JSON.stringify(template);
                
                const hasPreviewImage = template.preview_image && template.preview_image.trim() !== '';
                
                templateCard.innerHTML = `
                    <div class="template-image">
                        ${hasPreviewImage ? 
                            `<img src="${template.preview_image}" alt="${template.name}">` : 
                            createTemplatePreview(template.styles)}
                    </div>
                    <div class="template-info">
                        <h3>${template.name}</h3>
                        <p>${template.description || 'No description available'}</p>
                    </div>
                `;
                
                // Add click handler to select template
                templateCard.addEventListener('click', function() {
                    // Remove selected class from all templates
                    document.querySelectorAll('.template-card').forEach(card => {
                        card.classList.remove('selected');
                    });
                    
                    // Add selected class to clicked template
                    this.classList.add('selected');
                    
                    // Store selected template
                    selectedTemplate = {
                        id: key,
                        ...template
                    };
                    
                    // Update selected template display in form
                    selectedTemplateName.textContent = template.name;
                    updateSelectedTemplatePreview(template);
                });
                
                templatesGrid.appendChild(templateCard);
            });
            
            // Helper function to create a visual preview for templates without images
            function createTemplatePreview(styles) {
                const titleStyles = styles?.title_slide || {};
                const contentStyles = styles?.content_slide || {};
                
                // Get background colors
                const titleBg = titleStyles.background?.type === 'solid' && titleStyles.background.color ?
                    `rgb(${titleStyles.background.color.r}, ${titleStyles.background.color.g}, ${titleStyles.background.color.b})` :
                    '#ffffff';
                
                const contentBg = contentStyles.background?.type === 'solid' && contentStyles.background.color ?
                    `rgb(${contentStyles.background.color.r}, ${contentStyles.background.color.g}, ${contentStyles.background.color.b})` :
                    '#ffffff';
                
                return `
                    <div style="width: 100%; height: 100%; display: flex; flex-direction: column;">
                        <div style="flex: 1; background-color: ${titleBg}; display: flex; justify-content: center; align-items: center;">
                            <div style="width: 60%; height: 10px; background-color: #ddd; border-radius: 5px;"></div>
                        </div>
                        <div style="flex: 1; background-color: ${contentBg}; padding: 5px;">
                            <div style="width: 40%; height: 5px; background-color: #ddd; margin-bottom: 5px; border-radius: 3px;"></div>
                            <div style="width: 90%; height: 4px; background-color: #ddd; margin-bottom: 3px; border-radius: 2px;"></div>
                            <div style="width: 85%; height: 4px; background-color: #ddd; margin-bottom: 3px; border-radius: 2px;"></div>
                            <div style="width: 80%; height: 4px; background-color: #ddd; border-radius: 2px;"></div>
                        </div>
                    </div>
                `;
            }
            
            // Select first template by default
            if (templatesGrid.children.length > 0) {
                templatesGrid.children[0].click();
            }
            
        } catch (error) {
            console.error('Error loading templates:', error);
            templatesGrid.innerHTML = `
                <div class="template-error">
                    <p>Error loading templates: ${error.message}</p>
                    <button id="retry-templates" class="btn">Retry</button>
                </div>
            `;
            
            // Add retry button handler
            document.getElementById('retry-templates')?.addEventListener('click', loadTemplates);
        }
    }
    
    // Update the selected template preview in the form
    function updateSelectedTemplatePreview(template) {
        selectedTemplatePreview.innerHTML = '';
        
        // Create a visual preview of the template
        const previewVisual = document.createElement('div');
        previewVisual.className = 'template-visual-preview';
        
        // Get template styles
        const styles = template.styles || {};
        const titleSlideStyles = styles.title_slide || {};
        const contentSlideStyles = styles.content_slide || {};
        
        // Style the preview based on template
        previewVisual.innerHTML = `
            <div class="template-preview-slide" style="
                background-color: ${titleSlideStyles.background?.type === 'solid' && titleSlideStyles.background.color ? 
                `rgb(${titleSlideStyles.background.color.r}, ${titleSlideStyles.background.color.g}, ${titleSlideStyles.background.color.b})` : '#ffffff'};
                padding: 15px;
                border-radius: 5px;
                margin-bottom: 10px;
                text-align: center;
            ">
                <h5 style="
                    color: ${titleSlideStyles.title_font?.color ? 
                    `rgb(${titleSlideStyles.title_font.color.r}, ${titleSlideStyles.title_font.color.g}, ${titleSlideStyles.title_font.color.b})` : '#000000'};
                    font-family: ${titleSlideStyles.title_font?.name || 'inherit'};
                    margin: 0;
                ">Title Slide</h5>
                
                <div class="image-placeholder" style="margin-top: 10px; padding: 10px; font-size: 0.8em;">
                    <div style="font-size: 16px;">🖼️</div>
                    <p style="margin: 0;">Image placeholder</p>
                </div>
            </div>
            
            <div class="template-preview-slide" style="
                background-color: ${contentSlideStyles.background?.type === 'solid' && contentSlideStyles.background.color ? 
                `rgb(${contentSlideStyles.background.color.r}, ${contentSlideStyles.background.color.g}, ${contentSlideStyles.background.color.b})` : '#ffffff'};
                padding: 15px;
                border-radius: 5px;
                text-align: left;
            ">
                <h5 style="
                    color: ${contentSlideStyles.title_font?.color ? 
                    `rgb(${contentSlideStyles.title_font.color.r}, ${contentSlideStyles.title_font.color.g}, ${contentSlideStyles.title_font.color.b})` : '#000000'};
                    font-family: ${contentSlideStyles.title_font?.name || 'inherit'};
                    margin: 0 0 10px 0;
                ">Content Slide</h5>
                
                <ul style="
                    margin: 0;
                    padding-left: 20px;
                    font-size: 0.8em;
                    color: ${contentSlideStyles.body_font?.color ? 
                    `rgb(${contentSlideStyles.body_font.color.r}, ${contentSlideStyles.body_font.color.g}, ${contentSlideStyles.body_font.color.b})` : '#333333'};
                ">
                    <li>Bullet point 1</li>
                    <li>Bullet point 2</li>
                </ul>
                
                <div class="image-placeholder" style="margin-top: 10px; padding: 10px; font-size: 0.8em;">
                    <div style="font-size: 16px;">🖼️</div>
                    <p style="margin: 0;">Image placeholder</p>
                </div>
            </div>
        `;
        
        selectedTemplatePreview.appendChild(previewVisual);
    }
    
    // Edit button handler
    editBtn.addEventListener('click', function() {
        previewSection.classList.add('hidden');
        generateEditor(presentationData.content);
        editorSection.classList.remove('hidden');
    });
    
    // Download button handler
    downloadBtn.addEventListener('click', function() {
        window.location.href = presentationData.download_url;
    });

    // Presentation preview button handler
    presentationPreviewBtn.addEventListener('click', function() {
        openFullScreenPreview();
    });
    
    // Generate editor interface
    function generateEditor(content) {
        const editorContainer = document.getElementById('editor-content');
        editorContainer.innerHTML = '';
        
        // Title editor
        const titleEditor = document.createElement('div');
        titleEditor.className = 'editor-item';
        
        const titleLabel = document.createElement('label');
        titleLabel.textContent = 'Presentation Title:';
        titleEditor.appendChild(titleLabel);
        
        const titleInput = document.createElement('input');
        titleInput.type = 'text';
        titleInput.className = 'form-control editor-title';
        titleInput.value = content.title;
        titleInput.id = 'edit-presentation-title';
        titleEditor.appendChild(titleInput);
        
        editorContainer.appendChild(titleEditor);
        
        // Slides editor
        content.slides.forEach((slide, index) => {
            const slideEditor = document.createElement('div');
            slideEditor.className = 'slide-editor';
            
            const slideHeader = document.createElement('h3');
            slideHeader.textContent = `Slide ${index + 1}`;
            slideEditor.appendChild(slideHeader);
            
            const slideTitleLabel = document.createElement('label');
            slideTitleLabel.textContent = 'Slide Title:';
            slideEditor.appendChild(slideTitleLabel);
            
            const slideTitleInput = document.createElement('input');
            slideTitleInput.type = 'text';
            slideTitleInput.className = 'form-control slide-title';
            slideTitleInput.value = slide.title;
            slideTitleInput.dataset.slideIndex = index;
            slideEditor.appendChild(slideTitleInput);
            
            const pointsLabel = document.createElement('label');
            pointsLabel.textContent = 'Bullet Points:';
            slideEditor.appendChild(pointsLabel);
            
            slide.points.forEach((point, pointIndex) => {
                const pointInput = document.createElement('input');
                pointInput.type = 'text';
                pointInput.className = 'form-control slide-point';
                pointInput.value = point;
                pointInput.dataset.slideIndex = index;
                pointInput.dataset.pointIndex = pointIndex;
                slideEditor.appendChild(pointInput);
            });
            
            // If slide has an image prompt, show it
            if (presentationData.image_prompts && presentationData.image_prompts[index]) {
                const imagePromptLabel = document.createElement('label');
                imagePromptLabel.textContent = 'Image Prompt:';
                slideEditor.appendChild(imagePromptLabel);
                
                const imagePromptInput = document.createElement('input');
                imagePromptInput.type = 'text';
                imagePromptInput.className = 'form-control image-prompt-input';
                imagePromptInput.value = presentationData.image_prompts[index];
                imagePromptInput.dataset.slideIndex = index;
                imagePromptInput.readOnly = true; // Make it read-only
                slideEditor.appendChild(imagePromptInput);
            }
            
            editorContainer.appendChild(slideEditor);
        });
    }
    
    // Save changes button handler
    saveChangesBtn.addEventListener('click', async function() {
        editorSection.classList.add('hidden');
        loadingSection.classList.remove('hidden');
        updateStatus('Updating your presentation...');
        
        // Collect edited data
        const updatedContent = {
            title: document.getElementById('edit-presentation-title').value,
            slides: []
        };
        
        const slideEditors = document.querySelectorAll('.slide-editor');
        slideEditors.forEach((slideEditor, index) => {
            const titleInput = slideEditor.querySelector(`.slide-title[data-slide-index="${index}"]`);
            const pointInputs = slideEditor.querySelectorAll(`.slide-point[data-slide-index="${index}"]`);
            
            const slideData = {
                title: titleInput.value,
                points: []
            };
            
            pointInputs.forEach(input => {
                if (input.value.trim()) slideData.points.push(input.value);
            });
            
            updatedContent.slides.push(slideData);
        });
        
        try {
            const response = await fetch('/update_ppt', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    content: updatedContent,
                    image_prompts: presentationData.image_prompts,
                    template: presentationData.template
                })
            });
            
            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.error || 'Failed to update presentation');
            }
            
            const data = await response.json();
            
            // Update download link
            downloadLink.href = data.download_url;
            downloadLink.setAttribute('download', data.filename);
            
            // Update presentation data
            presentationData.download_url = data.download_url;
            presentationData.filename = data.filename;
            presentationData.content = updatedContent;
            presentationData.preview_data = data.preview_data;
            
            // Update HTML preview
            generateHtmlPreview(presentationData.preview_data);
            
            // Show result section
            loadingSection.classList.add('hidden');
            resultSection.classList.remove('hidden');
            
        } catch (error) {
            console.error('Error:', error);
            showError(error.message || 'An unexpected error occurred');
        }
    });
    
    // Cancel edit button handler
    cancelEditBtn.addEventListener('click', function() {
        editorSection.classList.add('hidden');
        previewSection.classList.remove('hidden');
    });
    
    // Try again button
    tryAgainBtn.addEventListener('click', function() {
        errorSection.classList.add('hidden');
        templateSelectionSection.classList.remove('hidden');
    });
    
    // Show error
    function showError(message) {
        errorMessage.textContent = message;
        loadingSection.classList.add('hidden');
        templateSelectionSection.classList.add('hidden');
        contentFormSection.classList.add('hidden');
        previewSection.classList.add('hidden');
        editorSection.classList.add('hidden');
        resultSection.classList.add('hidden');
        errorSection.classList.remove('hidden');
    }
    
    // Update status message
    function updateStatus(message) {
        statusMessage.textContent = message;
        statusMessage.style.animation = 'none';
        setTimeout(() => {
            statusMessage.style.animation = 'fadeIn 0.5s';
        }, 10);
    }
    
    // Cycle status messages
    function cycleStatusMessages() {
        currentStatusIndex = (currentStatusIndex + 1) % statusMessages.length;
        updateStatus(statusMessages[currentStatusIndex]);
    }
});