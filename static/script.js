document.addEventListener('DOMContentLoaded', function() {
    const templateSelectionSection = document.getElementById('template-selection');
    const templatesGrid = document.getElementById('templates-grid');
    const continueToContentBtn = document.getElementById('continue-to-content');
    const contentFormSection = document.getElementById('content-form');
    const selectedTemplateName = document.getElementById('selected-template-name');
    const selectedTemplatePreview = document.getElementById('selected-template-preview');
    const backToTemplatesBtn = document.getElementById('back-to-templates');
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
    const downloadBtn = document.getElementById('download-btn');
    const editBtn = document.getElementById('edit-btn');
    const presentationPreviewBtn = document.getElementById('presentation-preview-btn');
    const saveChangesBtn = document.getElementById('save-changes-btn');
    const cancelEditBtn = document.getElementById('cancel-edit-btn');
    
    let presentationData = null;
    let selectedTemplate = null;
    
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

    loadTemplates();
    
    continueToContentBtn.addEventListener('click', function() {
        if (!selectedTemplate) {
            alert('Please select a template before continuing');
            return;
        }
        templateSelectionSection.classList.add('hidden');
        contentFormSection.classList.remove('hidden');
    });
    
    backToTemplatesBtn.addEventListener('click', function() {
        contentFormSection.classList.add('hidden');
        templateSelectionSection.classList.remove('hidden');
    });
    
    form.addEventListener('submit', async function(e) {
        e.preventDefault();
        const topic = document.getElementById('topic').value.trim();
        const numSlides = parseInt(document.getElementById('num_slides').value, 10);
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
        contentFormSection.classList.add('hidden');
        loadingSection.classList.remove('hidden');
        generateBtn.disabled = true;
        currentStatusIndex = 0;
        updateStatus(statusMessages[currentStatusIndex]);
        statusInterval = setInterval(cycleStatusMessages, 3000);
        try {
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
            clearInterval(statusInterval);
            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.error || 'Failed to generate presentation');
            }
            const data = await response.json();
            presentationData = {
                content: data.content,
                image_prompts: data.image_prompts,
                template: data.template,
                preview_data: data.preview_data,
                download_url: data.download_url,
                filename: data.filename
            };
            updateStatus('Presentation ready!');
            generateHtmlPreview(presentationData.preview_data);
            downloadLink.href = data.download_url;
            downloadLink.setAttribute('download', data.filename);
            loadingSection.classList.add('hidden');
            previewSection.classList.remove('hidden');
        } catch (error) {
            clearInterval(statusInterval);
            console.error('Error generating presentation:', error);
            showError(error.message || 'An unexpected error occurred');
        } finally {
            generateBtn.disabled = false;
        }
    });
    
    function generateHtmlPreview(previewData) {
        previewContent.innerHTML = '';
        if (!previewData || !previewData.slides || previewData.slides.length === 0) {
            previewContent.innerHTML = '<p>No preview data available</p>';
            return;
        }
        const pptTitle = previewData.title || 'Presentation';
        const titleSlideStyles = previewData.styles?.title_slide || {};
        const contentSlideStyles = previewData.styles?.content_slide || {};
        const imageSlideStyles = previewData.styles?.image_slide || {};
        
        const previewTitle = document.createElement('h3');
        previewTitle.className = 'preview-title';
        previewTitle.textContent = pptTitle;
        previewContent.appendChild(previewTitle);
        
        previewData.slides.forEach((slide, index) => {
            const slidePreview = document.createElement('div');
            slidePreview.className = 'slide-preview';
            const isTitle = slide.type === 'title';
            const slideStyles = isTitle ? titleSlideStyles : contentSlideStyles;
            const bgSettings = slideStyles.background || {};
            const bgImage = slideStyles.background_image || '';
            if (bgImage) {
                const img = new Image();
                img.src = `/static/${bgImage}`;
                img.onload = () => {
                    console.log(`Background image loaded for slide ${index + 1}: /static/${bgImage}`);
                    slidePreview.style.backgroundImage = `url('/static/${bgImage}')`;
                    slidePreview.style.backgroundSize = 'cover';
                    slidePreview.style.backgroundPosition = 'center';
                };
                img.onerror = () => {
                    console.error(`Failed to load background image for slide ${index + 1}: /static/${bgImage}`);
                    applyFallbackBackground(slidePreview, bgSettings, isTitle);
                };
            } else {
                applyFallbackBackground(slidePreview, bgSettings, isTitle);
            }
            
            const slideTitle = document.createElement('h4');
            const titleFont = slideStyles.title_font || {};
            slideTitle.textContent = slide.title || `Slide ${index + 1}`;
            slideTitle.style.position = 'absolute';
            slideTitle.style.left = isTitle ? '80px' : '40px';
            slideTitle.style.top = isTitle ? '160px' : '40px';
            slideTitle.style.width = isTitle ? '640px' : '720px';
            slideTitle.style.wordWrap = 'break-word'; // Enable wrapping
            slideTitle.style.overflowWrap = 'break-word';
            slideTitle.style.whiteSpace = 'normal';
            slideTitle.style.maxHeight = isTitle ? '160px' : '100px'; // Limit vertical overflow
            slideTitle.style.overflow = 'hidden';
            if (titleFont.name) slideTitle.style.fontFamily = titleFont.name;
            let fontSize = titleFont.size || (isTitle ? 44 : 32);
            if (slide.title.length > 40) {
                fontSize = Math.max(fontSize - 8, 20); // Reduce font size for long titles
                console.log(`Reduced font size for slide ${index + 1} title: ${slide.title.substring(0, 20)}... to ${fontSize}px`);
            }
            slideTitle.style.fontSize = `${fontSize}px`;
            if (titleFont.bold) slideTitle.style.fontWeight = 'bold';
            const titleColor = titleFont.color || {r: 0, g: 0, b: 0};
            slideTitle.style.color = `rgb(${titleColor.r}, ${titleColor.g}, ${titleColor.b})`;
            slideTitle.style.textAlign = titleFont.alignment || (isTitle ? 'center' : 'left');
            slidePreview.appendChild(slideTitle);
            
            if (!isTitle && slide.points && slide.points.length > 0) {
                const pointsList = document.createElement('ul');
                pointsList.style.position = 'absolute';
                pointsList.style.left = '40px';
                pointsList.style.top = '120px';
                pointsList.style.width = '400px';
                pointsList.style.paddingLeft = '20px';
                slide.points.forEach((point, pointIndex) => {
                    const pointItem = document.createElement('li');
                    pointItem.textContent = point;
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
            
            if (slide.has_image && slide.image_prompt && slide.image_style) {
                const imagePlaceholder = document.createElement('div');
                imagePlaceholder.className = 'image-placeholder';
                imagePlaceholder.style.position = 'absolute';
                imagePlaceholder.style.left = `${slide.image_style.left * 80}px`;
                imagePlaceholder.style.top = `${slide.image_style.top * 80}px`;
                imagePlaceholder.style.width = `${slide.image_style.width * 80}px`;
                imagePlaceholder.style.height = `${slide.image_style.height * 80}px`;
                imagePlaceholder.style.backgroundColor = `rgb(${slide.image_style.fill_color?.r || 245}, ${slide.image_style.fill_color?.g || 245}, ${slide.image_style.fill_color?.b || 245})`;
                imagePlaceholder.style.border = `${slide.image_style.border_width || 1.5}px ${slide.image_style.border_style || 'dashed'} rgb(${slide.image_style.border_color?.r || 200}, ${slide.image_style.border_color?.g || 200}, ${slide.image_style.border_color?.b || 200})`;
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

    function applyFallbackBackground(element, bgSettings, isTitle) {
        if (bgSettings.type === 'solid') {
            const bgColor = bgSettings.color || {r: isTitle ? 240 : 255, g: isTitle ? 240 : 255, b: isTitle ? 240 : 255};
            element.style.backgroundColor = `rgb(${bgColor.r}, ${bgColor.g}, ${bgColor.b})`;
            console.log(`Applied solid background: rgb(${bgColor.r}, ${bgColor.g}, ${bgColor.b})`);
        } else if (bgSettings.type === 'gradient') {
            const startColor = bgSettings.gradient_start || {r: 240, g: 240, b: 240};
            const endColor = bgSettings.gradient_end || {r: 200, g: 200, b: 200};
            const direction = bgSettings.gradient_direction || 'diagonal';
            element.style.background = `linear-gradient(${direction === 'diagonal' ? '135deg' : 'to bottom'}, rgb(${startColor.r}, ${startColor.g}, ${startColor.b}) 0%, rgb(${endColor.r}, ${endColor.g}, ${endColor.b}) 100%)`;
            console.log(`Applied gradient background: ${direction} from rgb(${startColor.r}, ${startColor.g}, ${startColor.b}) to rgb(${endColor.r}, ${endColor.g}, ${endColor.b})`);
        } else {
            element.style.backgroundColor = isTitle ? '#f0f0f0' : '#ffffff';
            console.log(`Applied default background: ${isTitle ? '#f0f0f0' : '#ffffff'}`);
        }
    }

    function openFullScreenPreview() {
        if (!presentationData || !presentationData.preview_data) {
            showError('Preview data not available');
            return;
        }
        const previewData = presentationData.preview_data;
        const modal = document.createElement('div');
        modal.className = 'presentation-modal';
        const titleSlideStyles = previewData.styles?.title_slide || {};
        const contentSlideStyles = previewData.styles?.content_slide || {};
        const imageSlideStyles = previewData.styles?.image_slide || {};
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
                        const bgSettings = slideStyles.background || {};
                        const bgImage = slideStyles.background_image || '';
                        let bgStyle = '';
                        if (bgImage) {
                            bgStyle = `background-image: url('/static/${bgImage}'); background-size: cover; background-position: center`;
                            const img = new Image();
                            img.src = `/static/${bgImage}`;
                            img.onload = () => console.log(`Full-screen background image loaded for slide ${index + 1}: /static/${bgImage}`);
                            img.onerror = () => console.error(`Failed to load full-screen background image for slide ${index + 1}: /static/${bgImage}`);
                        } else if (bgSettings.type === 'solid') {
                            const bgColor = bgSettings.color || {r: isTitle ? 240 : 255, g: isTitle ? 240 : 255, b: isTitle ? 240 : 255};
                            bgStyle = `background-color: rgb(${bgColor.r}, ${bgColor.g}, ${bgColor.b})`;
                        } else if (bgSettings.type === 'gradient') {
                            const startColor = bgSettings.gradient_start || {r: 240, g: 240, b: 240};
                            const endColor = bgSettings.gradient_end || {r: 200, g: 200, b: 200};
                            const direction = bgSettings.gradient_direction || 'diagonal';
                            bgStyle = `background: linear-gradient(${direction === 'diagonal' ? '135deg' : 'to bottom'}, rgb(${startColor.r}, ${startColor.g}, ${startColor.b}) 0%, rgb(${endColor.r}, ${endColor.g}, ${endColor.b}) 100%)`;
                        }
                        const titleFont = slideStyles.title_font || {};
                        const titleColor = titleFont.color || {r: 0, g: 0, b: 0};
                        let fontSize = titleFont.size || (isTitle ? 44 : 32);
                        if (slide.title.length > 40) {
                            fontSize = Math.max(fontSize - 8, 20); // Reduce font size for long titles
                            console.log(`Reduced font size for full-screen slide ${index + 1} title: ${slide.title.substring(0, 20)}... to ${fontSize}px`);
                        }
                        return `
                            <div class="presentation-slide ${index === 0 ? 'active' : ''}" style="${bgStyle}">
                                <div class="slide-inner ${isTitle ? 'title-slide' : 'content-slide'}">
                                    <h2 style="
                                        position: absolute;
                                        left: ${isTitle ? '80px' : '40px'};
                                        top: ${isTitle ? '160px' : '40px'};
                                        width: ${isTitle ? '640px' : '720px'};
                                        color: rgb(${titleColor.r}, ${titleColor.g}, ${titleColor.b});
                                        font-family: ${titleFont.name || 'inherit'};
                                        font-size: ${fontSize}px;
                                        font-weight: ${titleFont.bold ? 'bold' : 'normal'};
                                        text-align: ${titleFont.alignment || (isTitle ? 'center' : 'left')};
                                        word-wrap: break-word;
                                        overflow-wrap: break-word;
                                        white-space: normal;
                                        max-height: ${isTitle ? '160px' : '100px'};
                                        overflow: hidden;
                                    ">
                                        ${slide.title || `Slide ${index + 1}`}
                                    </h2>
                                    ${isTitle ? renderTitleSlideContent(slide, imageSlideStyles) : renderContentSlideContent(slide, imageSlideStyles)}
                                </div>
                            </div>
                        `;
                    }).join('')}
                </div>
            </div>
        `;
        
        function renderTitleSlideContent(slide, imageSlideStyles) {
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
        
        function renderContentSlideContent(slide, imageSlideStyles) {
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
        
        document.body.appendChild(modal);
        const closeBtn = modal.querySelector('.close-btn');
        const prevBtn = modal.querySelector('.prev-btn');
        const nextBtn = modal.querySelector('.next-btn');
        const slides = modal.querySelectorAll('.presentation-slide');
        const slideCounter = modal.querySelector('.slide-counter');
        let currentSlide = 0;
        closeBtn.addEventListener('click', () => {
            document.body.removeChild(modal);
        });
        prevBtn.addEventListener('click', () => {
            slides[currentSlide].classList.remove('active');
            currentSlide = (currentSlide - 1 + slides.length) % slides.length;
            slides[currentSlide].classList.add('active');
            slideCounter.textContent = `${currentSlide + 1} / ${slides.length}`;
        });
        nextBtn.addEventListener('click', () => {
            slides[currentSlide].classList.remove('active');
            currentSlide = (currentSlide + 1) % slides.length;
            slides[currentSlide].classList.add('active');
            slideCounter.textContent = `${currentSlide + 1} / ${slides.length}`;
        });
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
    
    async function loadTemplates() {
        try {
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
            templatesGrid.innerHTML = '';
            if (Object.keys(data.templates).length === 0) {
                templatesGrid.innerHTML = `
                    <div class="no-templates">
                        <p>No templates available. Please check your template directory.</p>
                    </div>
                `;
                return;
            }
            Object.entries(data.templates).forEach(([key, template]) => {
                const templateCard = document.createElement('div');
                templateCard.className = 'template-card';
                templateCard.dataset.templateId = key;
                templateCard.dataset.templateInfo = JSON.stringify(template);
                const hasPreviewImage = template.preview_image && template.preview_image.trim() !== '';
                templateCard.innerHTML = `
                    <div class="template-image">
                        ${hasPreviewImage ? 
                            `<img src="/static/${template.preview_image}" alt="${template.name}" onerror="this.onerror=null; console.error('Failed to load preview image for template ${key}: /static/${template.preview_image}'); this.parentNode.innerHTML = createTemplatePreview(${JSON.stringify(template.styles)});">` : 
                            createTemplatePreview(template.styles)}
                    </div>
                    <div class="template-info">
                        <h3>${template.name}</h3>
                        <p>${template.description || 'No description available'}</p>
                    </div>
                `;
                if (hasPreviewImage) {
                    const img = new Image();
                    img.src = `/static/${template.preview_image}`;
                    img.onload = () => console.log(`Preview image loaded for template ${key}: /static/${template.preview_image}`);
                    img.onerror = () => console.error(`Failed to load preview image for template ${key}: /static/${template.preview_image}`);
                }
                
                templateCard.addEventListener('click', function() {
                    document.querySelectorAll('.template-card').forEach(card => {
                        card.classList.remove('selected');
                    });
                    this.classList.add('selected');
                    selectedTemplate = {
                        id: key,
                        ...template
                    };
                    selectedTemplateName.textContent = template.name;
                    updateSelectedTemplatePreview(template);
                });
                templatesGrid.appendChild(templateCard);
            });
            
            function createTemplatePreview(styles) {
                const titleStyles = styles?.title_slide || {};
                const contentStyles = styles?.content_slide || {};
                let titleBg = '#ffffff';
                if (titleStyles.background_image) {
                    titleBg = `url('/static/${titleStyles.background_image}')`;
                    const img = new Image();
                    img.src = `/static/${titleStyles.background_image}`;
                    img.onload = () => console.log(`Template preview background image loaded for title slide: /static/${titleStyles.background_image}`);
                    img.onerror = () => console.error(`Failed to load template preview background image for title slide: /static/${titleStyles.background_image}`);
                } else if (titleStyles.background?.type === 'solid') {
                    const color = titleStyles.background.color || {r: 255, g: 255, b: 255};
                    titleBg = `rgb(${color.r}, ${color.g}, ${color.b})`;
                } else if (titleStyles.background?.type === 'gradient') {
                    const startColor = titleStyles.background.gradient_start || {r: 240, g: 240, b: 240};
                    const endColor = titleStyles.background.gradient_end || {r: 200, g: 200, b: 200};
                    titleBg = `linear-gradient(135deg, rgb(${startColor.r}, ${startColor.g}, ${startColor.b}) 0%, rgb(${endColor.r}, ${startColor.g}, ${endColor.b}) 100%)`;
                }
                let contentBg = '#ffffff';
                if (contentStyles.background_image) {
                    contentBg = `url('/static/${contentStyles.background_image}')`;
                    const img = new Image();
                    img.src = `/static/${contentStyles.background_image}`;
                    img.onload = () => console.log(`Template preview background image loaded for content slide: /static/${contentStyles.background_image}`);
                    img.onerror = () => console.error(`Failed to load template preview background image for content slide: /static/${contentStyles.background_image}`);
                } else if (contentStyles.background?.type === 'solid') {
                    const color = contentStyles.background.color || {r: 255, g: 255, b: 255};
                    contentBg = `rgb(${color.r}, ${color.g}, ${color.b})`;
                } else if (contentStyles.background?.type === 'gradient') {
                    const startColor = contentStyles.background.gradient_start || {r: 255, g: 255, b: 255};
                    const endColor = contentStyles.background.gradient_end || {r: 200, g: 200, b: 200};
                    contentBg = `linear-gradient(to bottom, rgb(${startColor.r}, ${startColor.g}, ${startColor.b}) 0%, rgb(${endColor.r}, ${endColor.g}, ${endColor.b}) 100%)`;
                }
                return `
                    <div style="width: 100%; height: 100%; display: flex; flex-direction: column;">
                        <div style="flex: 1; background: ${titleBg}; background-size: cover; background-position: center; display: flex; justify-content: center; align-items: center;">
                            <div style="width: 60%; height: 10px; background-color: #ddd; border-radius: 5px;"></div>
                        </div>
                        <div style="flex: 1; background: ${contentBg}; background-size: cover; background-position: center; padding: 5px;">
                            <div style="width: 40%; height: 5px; background-color: #ddd; margin-bottom: 5px; border-radius: 3px;"></div>
                            <div style="width: 90%; height: 4px; background-color: #ddd; margin-bottom: 3px; border-radius: 2px;"></div>
                            <div style="width: 85%; height: 4px; background-color: #ddd; margin-bottom: 3px; border-radius: 2px;"></div>
                            <div style="width: 80%; height: 4px; background-color: #ddd; border-radius: 2px;"></div>
                        </div>
                    </div>
                `;
            }
            
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
            document.getElementById('retry-templates')?.addEventListener('click', loadTemplates);
        }
    }
    
    function updateSelectedTemplatePreview(template) {
        selectedTemplatePreview.innerHTML = '';
        const previewVisual = document.createElement('div');
        previewVisual.className = 'template-visual-preview';
        const styles = template.styles || {};
        const titleSlideStyles = styles.title_slide || {};
        const contentSlideStyles = styles.content_slide || {};
        const imageSlideStyles = styles.image_slide || {};
        let titleBgStyle = '#ffffff';
        if (titleSlideStyles.background_image) {
            titleBgStyle = `url('/static/${titleSlideStyles.background_image}')`;
            const img = new Image();
            img.src = `/static/${titleSlideStyles.background_image}`;
            img.onload = () => console.log(`Selected template preview background image loaded for title slide: /static/${titleSlideStyles.background_image}`);
            img.onerror = () => console.error(`Failed to load selected template preview background image for title slide: /static/${titleSlideStyles.background_image}`);
        } else if (titleSlideStyles.background?.type === 'solid') {
            const color = titleSlideStyles.background.color || {r: 240, g: 240, b: 240};
            titleBgStyle = `rgb(${color.r}, ${color.g}, ${color.b})`;
        } else if (titleSlideStyles.background?.type === 'gradient') {
            const startColor = titleSlideStyles.background.gradient_start || {r: 240, g: 240, b: 240};
            const endColor = titleSlideStyles.background.gradient_end || {r: 200, g: 200, b: 200};
            titleBgStyle = `linear-gradient(135deg, rgb(${startColor.r}, ${startColor.g}, ${startColor.b}) 0%, rgb(${endColor.r}, ${endColor.g}, ${endColor.b}) 100%)`;
        }
        let contentBgStyle = '#ffffff';
        if (contentSlideStyles.background_image) {
            contentBgStyle = `url('/static/${contentSlideStyles.background_image}')`;
            const img = new Image();
            img.src = `/static/${contentSlideStyles.background_image}`;
            img.onload = () => console.log(`Selected template preview background image loaded for content slide: /static/${contentSlideStyles.background_image}`);
            img.onerror = () => console.error(`Failed to load selected template preview background image for content slide: /static/${contentSlideStyles.background_image}`);
        } else if (contentSlideStyles.background?.type === 'solid') {
            const color = contentSlideStyles.background.color || {r: 255, g: 255, b: 255};
            contentBgStyle = `rgb(${color.r}, ${color.g}, ${color.b})`;
        } else if (contentSlideStyles.background?.type === 'gradient') {
            const startColor = contentSlideStyles.background.gradient_start || {r: 255, g: 255, b: 255};
            const endColor = contentSlideStyles.background.gradient_end || {r: 200, g: 200, b: 200};
            contentBgStyle = `linear-gradient(to bottom, rgb(${startColor.r}, ${startColor.g}, ${startColor.b}) 0%, rgb(${endColor.r}, ${endColor.g}, ${endColor.b}) 100%)`;
        }
        const titleImagePosition = titleSlideStyles.image_position || {left: 2.5, top: 4.0, width: 5.0, height: 2.5};
        const contentImagePosition = contentSlideStyles.image_position || {left: 6.0, top: 1.5, width: 3.5, height: 4.5};
        previewVisual.innerHTML = `
            <div class="template-preview-slide" style="
                background: ${titleBgStyle};
                background-size: cover;
                background-position: center;
                padding: 15px;
                border-radius: 5px;
                margin-bottom: 10px;
                text-align: center;
                position: relative;
            ">
                <h5 style="
                    color: ${titleSlideStyles.title_font?.color ? 
                    `rgb(${titleSlideStyles.title_font.color.r}, ${titleSlideStyles.title_font.color.g}, ${titleSlideStyles.title_font.color.b})` : '#000000'};
                    font-family: ${titleSlideStyles.title_font?.name || 'inherit'};
                    margin: 0;
                ">Title Slide</h5>
                <div class="image-placeholder" style="
                    position: absolute;
                    left: ${titleImagePosition.left * 10}px;
                    top: ${titleImagePosition.top * 10}px;
                    width: ${titleImagePosition.width * 10}px;
                    height: ${titleImagePosition.height * 10}px;
                    background-color: rgb(${imageSlideStyles.fill_color?.r || 245}, ${imageSlideStyles.fill_color?.g || 245}, ${imageSlideStyles.fill_color?.b || 245});
                    border: ${imageSlideStyles.border_width || 1.5}px ${imageSlideStyles.border_style || 'dashed'} rgb(${imageSlideStyles.border_color?.r || 200}, ${imageSlideStyles.border_color?.g || 200}, ${imageSlideStyles.border_color?.b || 200});
                    margin-top: 10px;
                    padding: 10px;
                    font-size: 0.8em;
                ">
                    <div style="font-size: 16px;">🖼️</div>
                    <p style="
                        margin: 0;
                        font-style: italic;
                        font-size: 12px;
                        color: #646464;
                    ">Image placeholder</p>
                </div>
            </div>
            <div class="template-preview-slide" style="
                background: ${contentBgStyle};
                background-size: cover;
                background-position: center;
                padding: 15px;
                border-radius: 5px;
                text-align: left;
                position: relative;
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
                <div class="image-placeholder" style="
                    position: absolute;
                    left: ${contentImagePosition.left * 10}px;
                    top: ${contentImagePosition.top * 10}px;
                    width: ${contentImagePosition.width * 10}px;
                    height: ${contentImagePosition.height * 10}px;
                    background-color: rgb(${imageSlideStyles.fill_color?.r || 245}, ${imageSlideStyles.fill_color?.g || 245}, ${imageSlideStyles.fill_color?.b || 245});
                    border: ${imageSlideStyles.border_width || 1.5}px ${imageSlideStyles.border_style || 'dashed'} rgb(${imageSlideStyles.border_color?.r || 200}, ${imageSlideStyles.border_color?.g || 200}, ${imageSlideStyles.border_color?.b || 200});
                    margin-top: 10px;
                    padding: 10px;
                    font-size: 0.8em;
                ">
                    <div style="font-size: 16px;">🖼️</div>
                    <p style="
                        margin: 0;
                        font-style: italic;
                        font-size: 12px;
                        color: #646464;
                    ">Image placeholder</p>
                </div>
            </div>
        `;
        selectedTemplatePreview.appendChild(previewVisual);
    }
    
    function generateEditor(content) {
        const editorContainer = document.getElementById('editor-content');
        editorContainer.innerHTML = '';
        
        // Presentation Title
        const titleEditor = document.createElement('div');
        titleEditor.className = 'editor-item';
        const titleLabel = document.createElement('label');
        titleLabel.textContent = 'Presentation Title:';
        titleEditor.appendChild(titleLabel);
        const titleInput = document.createElement('input');
        titleInput.type = 'text';
        titleInput.className = 'form-control editor-title';
        titleInput.value = content.title || '';
        titleInput.id = 'edit-presentation-title';
        titleEditor.appendChild(titleInput);
        editorContainer.appendChild(titleEditor);
        
        // Slides
        content.slides.forEach((slide, slideIndex) => {
            const slideEditor = document.createElement('div');
            slideEditor.className = 'slide-editor';
            const slideHeader = document.createElement('h3');
            slideHeader.textContent = `Slide ${slideIndex + 1}`;
            slideEditor.appendChild(slideHeader);
            
            // Slide Title
            const slideTitleLabel = document.createElement('label');
            slideTitleLabel.textContent = 'Slide Title:';
            const slideTitleInput = document.createElement('input');
            slideTitleInput.type = 'text';
            slideTitleInput.className = 'form-control';
            slideTitleInput.value = slide.title || '';
            slideTitleInput.id = `edit-slide-${slideIndex}-title`;
            slideEditor.appendChild(slideTitleLabel);
            slideEditor.appendChild(slideTitleInput);
            
            // Slide Points
            const pointsContainer = document.createElement('div');
            pointsContainer.className = 'points-editor';
            slide.points.forEach((point, pointIndex) => {
                const pointEditor = document.createElement('div');
                pointEditor.className = 'point-editor';
                const pointLabel = document.createElement('label');
                pointLabel.textContent = `Point ${pointIndex + 1}:`;
                const pointInput = document.createElement('textarea');
                pointInput.className = 'form-control';
                pointInput.value = point || '';
                pointInput.id = `edit-slide-${slideIndex}-point-${pointIndex}`;
                pointInput.rows = 2;
                pointEditor.appendChild(pointLabel);
                pointEditor.appendChild(pointInput);
                pointsContainer.appendChild(pointEditor);
            });
            slideEditor.appendChild(pointsContainer);
            
            // Image Prompt (Read-only)
            const imagePromptKey = slideIndex.toString();
            if (presentationData.image_prompts && presentationData.image_prompts[imagePromptKey]) {
                const imagePromptEditor = document.createElement('div');
                imagePromptEditor.className = 'image-prompt-editor';
                const imagePromptLabel = document.createElement('label');
                imagePromptLabel.textContent = 'Image Prompt:';
                const imagePromptInput = document.createElement('textarea');
                imagePromptInput.className = 'form-control';
                imagePromptInput.value = presentationData.image_prompts[imagePromptKey];
                imagePromptInput.readOnly = true;
                imagePromptInput.rows = 2;
                imagePromptEditor.appendChild(imagePromptLabel);
                imagePromptEditor.appendChild(imagePromptInput);
                slideEditor.appendChild(imagePromptEditor);
            }
            
            editorContainer.appendChild(slideEditor);
        });
    }
    
    editBtn.addEventListener('click', function() {
        if (!presentationData || !presentationData.content) {
            showError('No presentation data available for editing');
            return;
        }
        previewSection.classList.add('hidden');
        generateEditor(presentationData.content);
        editorSection.classList.remove('hidden');
    });
    
    saveChangesBtn.addEventListener('click', async function() {
        if (!presentationData) {
            showError('No presentation data available');
            return;
        }
        const updatedContent = {
            title: document.getElementById('edit-presentation-title').value.trim(),
            slides: []
        };
        
        // Collect slide data
        const slideEditors = document.querySelectorAll('.slide-editor');
        slideEditors.forEach((slideEditor, slideIndex) => {
            const slideTitle = document.getElementById(`edit-slide-${slideIndex}-title`).value.trim();
            const points = [];
            const pointInputs = slideEditor.querySelectorAll('.point-editor textarea');
            pointInputs.forEach((input) => {
                const pointText = input.value.trim();
                if (pointText) {
                    points.push(pointText);
                }
            });
            updatedContent.slides.push({
                title: slideTitle || `Slide ${slideIndex + 1}`,
                points: points
            });
        });
        
        if (!updatedContent.title) {
            showError('Presentation title cannot be empty');
            return;
        }
        if (updatedContent.slides.length === 0) {
            showError('At least one slide is required');
            return;
        }
        
        try {
            editorSection.classList.add('hidden');
            loadingSection.classList.remove('hidden');
            updateStatus('Updating presentation...');
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
            presentationData = {
                ...presentationData,
                content: updatedContent,
                preview_data: data.preview_data,
                download_url: data.download_url,
                filename: data.filename
            };
            generateHtmlPreview(presentationData.preview_data);
            downloadLink.href = data.download_url;
            downloadLink.setAttribute('download', data.filename);
            loadingSection.classList.add('hidden');
            previewSection.classList.remove('hidden');
            updateStatus('Presentation updated successfully!');
        } catch (error) {
            console.error('Error updating presentation:', error);
            showError(error.message || 'Failed to update presentation');
            editorSection.classList.remove('hidden');
            loadingSection.classList.add('hidden');
        }
    });
    
    cancelEditBtn.addEventListener('click', function() {
        editorSection.classList.add('hidden');
        previewSection.classList.remove('hidden');
    });
    
    downloadBtn.addEventListener('click', function() {
        if (presentationData && presentationData.download_url) {
            window.location.href = presentationData.download_url;
        }
    });

    presentationPreviewBtn.addEventListener('click', function() {
        openFullScreenPreview();
    });
    
    tryAgainBtn.addEventListener('click', function() {
        errorSection.classList.add('hidden');
        contentFormSection.classList.remove('hidden');
    });
    
    function cycleStatusMessages() {
        currentStatusIndex = (currentStatusIndex + 1) % statusMessages.length;
        updateStatus(statusMessages[currentStatusIndex]);
    }
    
    function updateStatus(message) {
        statusMessage.textContent = message;
    }
    
    function showError(message) {
        errorMessage.textContent = message;
        errorSection.classList.remove('hidden');
        loadingSection.classList.add('hidden');
        previewSection.classList.add('hidden');
        editorSection.classList.add('hidden');
    }
});

// document.addEventListener('DOMContentLoaded', function() {
//     const templateSelectionSection = document.getElementById('template-selection');
//     const templatesGrid = document.getElementById('templates-grid');
//     const continueToContentBtn = document.getElementById('continue-to-content');
//     const contentFormSection = document.getElementById('content-form');
//     const selectedTemplateName = document.getElementById('selected-template-name');
//     const selectedTemplatePreview = document.getElementById('selected-template-preview');
//     const backToTemplatesBtn = document.getElementById('back-to-templates');
//     const form = document.getElementById('ppt-form');
//     const generateBtn = document.getElementById('generate-btn');
//     const loadingSection = document.getElementById('loading');
//     const previewSection = document.getElementById('preview-section');
//     const previewContent = document.getElementById('preview-content');
//     const editorSection = document.getElementById('editor-section');
//     const resultSection = document.getElementById('result');
//     const downloadLink = document.getElementById('download-link');
//     const errorSection = document.getElementById('error');
//     const errorMessage = document.getElementById('error-message');
//     const tryAgainBtn = document.getElementById('try-again-btn');
//     const statusMessage = document.querySelector('.status-message');
//     const downloadBtn = document.getElementById('download-btn');
//     const editBtn = document.getElementById('edit-btn');
//     const presentationPreviewBtn = document.getElementById('presentation-preview-btn');
//     const saveChangesBtn = document.getElementById('save-changes-btn');
//     const cancelEditBtn = document.getElementById('cancel-edit-btn');
    
//     let presentationData = null;
//     let selectedTemplate = null;
    
//     const statusMessages = [
//         "Connecting to local Ollama service...",
//         "Generating presentation content...",
//         "Creating slide content...",
//         "Generating image prompts for slides...",
//         "Building PowerPoint presentation with selected template...",
//         "Finalizing your presentation..."
//     ];
//     let currentStatusIndex = 0;
//     let statusInterval;

//     loadTemplates();
    
//     continueToContentBtn.addEventListener('click', function() {
//         if (!selectedTemplate) {
//             alert('Please select a template before continuing');
//             return;
//         }
//         templateSelectionSection.classList.add('hidden');
//         contentFormSection.classList.remove('hidden');
//     });
    
//     backToTemplatesBtn.addEventListener('click', function() {
//         contentFormSection.classList.add('hidden');
//         templateSelectionSection.classList.remove('hidden');
//     });
    
//     form.addEventListener('submit', async function(e) {
//         e.preventDefault();
//         const topic = document.getElementById('topic').value.trim();
//         const numSlides = parseInt(document.getElementById('num_slides').value, 10);
//         if (!topic) {
//             showError('Please enter a presentation topic');
//             return;
//         }
//         if (isNaN(numSlides) || numSlides < 1 || numSlides > 20) {
//             showError('Number of slides must be between 1 and 20');
//             return;
//         }
//         if (!selectedTemplate) {
//             showError('Please select a template');
//             return;
//         }
//         contentFormSection.classList.add('hidden');
//         loadingSection.classList.remove('hidden');
//         generateBtn.disabled = true;
//         currentStatusIndex = 0;
//         updateStatus(statusMessages[currentStatusIndex]);
//         statusInterval = setInterval(cycleStatusMessages, 3000);
//         try {
//             const response = await fetch('/generate_ppt', {
//                 method: 'POST',
//                 headers: {
//                     'Content-Type': 'application/json',
//                 },
//                 body: JSON.stringify({
//                     topic: topic,
//                     num_slides: numSlides,
//                     template: selectedTemplate.id
//                 })
//             });
//             clearInterval(statusInterval);
//             if (!response.ok) {
//                 const errorData = await response.json();
//                 throw new Error(errorData.error || 'Failed to generate presentation');
//             }
//             const data = await response.json();
//             presentationData = {
//                 content: data.content,
//                 image_prompts: data.image_prompts,
//                 template: data.template,
//                 preview_data: data.preview_data,
//                 download_url: data.download_url,
//                 filename: data.filename
//             };
//             updateStatus('Presentation ready!');
//             generateHtmlPreview(presentationData.preview_data);
//             downloadLink.href = data.download_url;
//             downloadLink.setAttribute('download', data.filename);
//             loadingSection.classList.add('hidden');
//             previewSection.classList.remove('hidden');
//         } catch (error) {
//             clearInterval(statusInterval);
//             console.error('Error:', error);
//             showError(error.message || 'An unexpected error occurred');
//         } finally {
//             generateBtn.disabled = false;
//         }
//     });
    
//     function generateHtmlPreview(previewData) {
//         previewContent.innerHTML = '';
//         if (!previewData || !previewData.slides || previewData.slides.length === 0) {
//             previewContent.innerHTML = '<p>No preview data available</p>';
//             return;
//         }
//         const pptTitle = previewData.title || 'Presentation';
//         const titleSlideStyles = previewData.styles?.title_slide || {};
//         const contentSlideStyles = previewData.styles?.content_slide || {};
//         const imageSlideStyles = previewData.styles?.image_slide || {};
        
//         const previewTitle = document.createElement('h3');
//         previewTitle.className = 'preview-title';
//         previewTitle.textContent = pptTitle;
//         previewContent.appendChild(previewTitle);
        
//         previewData.slides.forEach((slide, index) => {
//             const slidePreview = document.createElement('div');
//             slidePreview.className = 'slide-preview';
//             const isTitle = slide.type === 'title';
//             const slideStyles = isTitle ? titleSlideStyles : contentSlideStyles;
//             const bgSettings = slideStyles.background || {};
//             if (bgSettings.type === 'solid') {
//                 const bgColor = bgSettings.color || {r: isTitle ? 240 : 255, g: isTitle ? 240 : 255, b: isTitle ? 240 : 255};
//                 slidePreview.style.backgroundColor = `rgb(${bgColor.r}, ${bgColor.g}, ${bgColor.b})`;
//             } else if (bgSettings.type === 'gradient') {
//                 const startColor = bgSettings.gradient_start || {r: 240, g: 240, b: 240};
//                 const endColor = bgSettings.gradient_end || {r: 200, g: 200, b: 200};
//                 const direction = bgSettings.gradient_direction || 'diagonal';
//                 slidePreview.style.background = `linear-gradient(${direction === 'diagonal' ? '45deg' : 'to bottom'}, rgb(${startColor.r}, ${startColor.g}, ${startColor.b}), rgb(${endColor.r}, ${endColor.g}, ${endColor.b}))`;
//             }
            
//             const slideTitle = document.createElement('h4');
//             const titleFont = slideStyles.title_font || {};
//             slideTitle.textContent = slide.title || `Slide ${index + 1}`;
//             slideTitle.style.position = 'absolute';
//             slideTitle.style.left = isTitle ? '80px' : '40px';
//             slideTitle.style.top = isTitle ? '160px' : '40px';
//             slideTitle.style.width = isTitle ? '640px' : '720px';
//             if (titleFont.name) slideTitle.style.fontFamily = titleFont.name;
//             if (titleFont.size) slideTitle.style.fontSize = `${titleFont.size}px`;
//             if (titleFont.bold) slideTitle.style.fontWeight = 'bold';
//             const titleColor = titleFont.color || {r: 0, g: 0, b: 0};
//             slideTitle.style.color = `rgb(${titleColor.r}, ${titleColor.g}, ${titleColor.b})`;
//             slideTitle.style.textAlign = titleFont.alignment || (isTitle ? 'center' : 'left');
//             slidePreview.appendChild(slideTitle);
            
//             if (!isTitle && slide.points && slide.points.length > 0) {
//                 const pointsList = document.createElement('ul');
//                 pointsList.style.position = 'absolute';
//                 pointsList.style.left = '40px';
//                 pointsList.style.top = '120px';
//                 pointsList.style.width = '400px';
//                 pointsList.style.paddingLeft = '20px';
//                 slide.points.forEach((point, pointIndex) => {
//                     const pointItem = document.createElement('li');
//                     pointItem.textContent = point;
//                     if (slide.points_styling && slide.points_styling[pointIndex]) {
//                         const styling = slide.points_styling[pointIndex];
//                         if (styling.font_name) pointItem.style.fontFamily = styling.font_name;
//                         if (styling.font_size) pointItem.style.fontSize = `${styling.font_size}px`;
//                         pointItem.style.color = `rgb(${styling.color?.r || 50}, ${styling.color?.g || 50}, ${styling.color?.b || 50})`;
//                         pointItem.style.textAlign = styling.alignment || 'left';
//                         pointItem.style.marginBottom = `${styling.space_after || 6}px`;
//                         pointItem.style.marginTop = `${styling.space_before || 6}px`;
//                     }
//                     pointsList.appendChild(pointItem);
//                 });
//                 slidePreview.appendChild(pointsList);
//             }
            
//             if (slide.has_image && slide.image_prompt && slide.image_style) {
//                 const imagePlaceholder = document.createElement('div');
//                 imagePlaceholder.className = 'image-placeholder';
//                 imagePlaceholder.style.position = 'absolute';
//                 imagePlaceholder.style.left = `${slide.image_style.left * 80}px`;
//                 imagePlaceholder.style.top = `${slide.image_style.top * 80}px`;
//                 imagePlaceholder.style.width = `${slide.image_style.width * 80}px`;
//                 imagePlaceholder.style.height = `${slide.image_style.height * 80}px`;
//                 imagePlaceholder.style.backgroundColor = `rgb(${slide.image_style.fill_color?.r || 245}, ${slide.image_style.fill_color?.g || 245}, ${slide.image_style.fill_color?.b || 245})`;
//                 imagePlaceholder.style.border = `${slide.image_style.border_width || 1.5}px ${slide.image_style.border_style || 'dashed'} rgb(${slide.image_style.border_color?.r || 200}, ${slide.image_style.border_color?.g || 200}, ${slide.image_style.border_color?.b || 200})`;
//                 const imageIcon = document.createElement('div');
//                 imageIcon.className = 'image-placeholder-icon';
//                 imageIcon.innerHTML = '🖼️';
//                 imageIcon.style.fontSize = '48px';
//                 imageIcon.style.marginBottom = '10px';
//                 imagePlaceholder.appendChild(imageIcon);
//                 const imageText = document.createElement('p');
//                 imageText.textContent = slide.image_prompt;
//                 imageText.style.margin = '0';
//                 imageText.style.fontStyle = 'italic';
//                 imageText.style.fontSize = '14px';
//                 imageText.style.color = '#646464';
//                 imagePlaceholder.appendChild(imageText);
//                 slidePreview.appendChild(imagePlaceholder);
//             }
            
//             previewContent.appendChild(slidePreview);
//         });
//     }

//     function openFullScreenPreview() {
//         if (!presentationData || !presentationData.preview_data) {
//             showError('Preview data not available');
//             return;
//         }
//         const previewData = presentationData.preview_data;
//         const modal = document.createElement('div');
//         modal.className = 'presentation-modal';
//         const titleSlideStyles = previewData.styles?.title_slide || {};
//         const contentSlideStyles = previewData.styles?.content_slide || {};
//         const imageSlideStyles = previewData.styles?.image_slide || {};
//         modal.innerHTML = `
//             <div class="presentation-container">
//                 <div class="presentation-toolbar">
//                     <button class="close-btn">×</button>
//                     <div class="slide-counter">1 / ${previewData.slides.length}</div>
//                     <div class="presentation-controls">
//                         <button class="prev-btn">◀</button>
//                         <button class="next-btn">▶</button>
//                     </div>
//                 </div>
//                 <div class="presentation-content">
//                     ${previewData.slides.map((slide, index) => {
//                         const isTitle = slide.type === 'title';
//                         const slideStyles = isTitle ? titleSlideStyles : contentSlideStyles;
//                         const bgSettings = slideStyles.background || {};
//                         let bgStyle = '';
//                         if (bgSettings.type === 'solid') {
//                             const bgColor = bgSettings.color || {r: isTitle ? 240 : 255, g: isTitle ? 240 : 255, b: isTitle ? 240 : 255};
//                             bgStyle = `background-color: rgb(${bgColor.r}, ${bgColor.g}, ${bgColor.b})`;
//                         } else if (bgSettings.type === 'gradient') {
//                             const startColor = bgSettings.gradient_start || {r: 240, g: 240, b: 240};
//                             const endColor = bgSettings.gradient_end || {r: 200, g: 200, b: 200};
//                             const direction = bgSettings.gradient_direction || 'diagonal';
//                             bgStyle = `background: linear-gradient(${direction === 'diagonal' ? '45deg' : 'to bottom'}, rgb(${startColor.r}, ${startColor.g}, ${startColor.b}), rgb(${endColor.r}, ${endColor.g}, ${endColor.b}))`;
//                         }
//                         const titleFont = slideStyles.title_font || {};
//                         const titleColor = titleFont.color || {r: 0, g: 0, b: 0};
//                         return `
//                             <div class="presentation-slide ${index === 0 ? 'active' : ''}" style="${bgStyle}">
//                                 <div class="slide-inner ${isTitle ? 'title-slide' : 'content-slide'}">
//                                     <h2 style="
//                                         position: absolute;
//                                         left: ${isTitle ? '80px' : '40px'};
//                                         top: ${isTitle ? '160px' : '40px'};
//                                         width: ${isTitle ? '640px' : '720px'};
//                                         color: rgb(${titleColor.r}, ${titleColor.g}, ${titleColor.b});
//                                         font-family: ${titleFont.name || 'inherit'};
//                                         font-size: ${titleFont.size || 44}px;
//                                         font-weight: ${titleFont.bold ? 'bold' : 'normal'};
//                                         text-align: ${titleFont.alignment || (isTitle ? 'center' : 'left')};
//                                     ">
//                                         ${slide.title || `Slide ${index + 1}`}
//                                     </h2>
//                                     ${isTitle ? renderTitleSlideContent(slide, imageSlideStyles) : renderContentSlideContent(slide, imageSlideStyles)}
//                                 </div>
//                             </div>
//                         `;
//                     }).join('')}
//                 </div>
//             </div>
//         `;
        
//         function renderTitleSlideContent(slide, imageSlideStyles) {
//             if (slide.has_image && slide.image_prompt && slide.image_style) {
//                 return `
//                     <div class="image-placeholder" style="
//                         position: absolute;
//                         left: ${slide.image_style.left * 80}px;
//                         top: ${slide.image_style.top * 80}px;
//                         width: ${slide.image_style.width * 80}px;
//                         height: ${slide.image_style.height * 80}px;
//                         background-color: rgb(${slide.image_style.fill_color?.r || 245}, ${slide.image_style.fill_color?.g || 245}, ${slide.image_style.fill_color?.b || 245});
//                         border: ${slide.image_style.border_width || 1.5}px ${slide.image_style.border_style || 'dashed'} rgb(${slide.image_style.border_color?.r || 200}, ${slide.image_style.border_color?.g || 200}, ${slide.image_style.border_color?.b || 200});
//                     ">
//                         <div class="image-placeholder-icon" style="font-size: 48px; margin-bottom: 10px;">🖼️</div>
//                         <p style="margin: 0; font-style: italic; font-size: 14px; color: #646464;">${slide.image_prompt}</p>
//                     </div>
//                 `;
//             }
//             return '';
//         }
        
//         function renderContentSlideContent(slide, imageSlideStyles) {
//             let pointsHtml = '';
//             if (slide.points && slide.points.length > 0) {
//                 pointsHtml = `
//                     <ul class="slide-points" style="
//                         position: absolute;
//                         left: 40px;
//                         top: 120px;
//                         width: 400px;
//                         padding-left: 20px;
//                     ">
//                         ${slide.points.map((point, i) => {
//                             const styling = slide.points_styling && slide.points_styling[i] ? slide.points_styling[i] : {};
//                             const color = styling.color || {r: 50, g: 50, b: 50};
//                             return `
//                                 <li style="
//                                     font-family: ${styling.font_name || 'inherit'};
//                                     font-size: ${styling.font_size || 18}px;
//                                     color: rgb(${color.r}, ${color.g}, ${color.b});
//                                     text-align: ${styling.alignment || 'left'};
//                                     margin-bottom: ${styling.space_after || 6}px;
//                                     margin-top: ${styling.space_before || 6}px;
//                                 ">
//                                     ${point}
//                                 </li>
//                             `;
//                         }).join('')}
//                     </ul>
//                 `;
//             }
//             let imageHtml = '';
//             if (slide.has_image && slide.image_prompt && slide.image_style) {
//                 imageHtml = `
//                     <div class="image-placeholder" style="
//                         position: absolute;
//                         left: ${slide.image_style.left * 80}px;
//                         top: ${slide.image_style.top * 80}px;
//                         width: ${slide.image_style.width * 80}px;
//                         height: ${slide.image_style.height * 80}px;
//                         background-color: rgb(${slide.image_style.fill_color?.r || 245}, ${slide.image_style.fill_color?.g || 245}, ${slide.image_style.fill_color?.b || 245});
//                         border: ${slide.image_style.border_width || 1.5}px ${slide.image_style.border_style || 'dashed'} rgb(${slide.image_style.border_color?.r || 200}, ${slide.image_style.border_color?.g || 200}, ${slide.image_style.border_color?.b || 200});
//                     ">
//                         <div class="image-placeholder-icon" style="font-size: 48px; margin-bottom: 10px;">🖼️</div>
//                         <p style="margin: 0; font-style: italic; font-size: 14px; color: #646464;">${slide.image_prompt}</p>
//                     </div>
//                 `;
//             }
//             return pointsHtml + imageHtml;
//         }
        
//         document.body.appendChild(modal);
//         const closeBtn = modal.querySelector('.close-btn');
//         const prevBtn = modal.querySelector('.prev-btn');
//         const nextBtn = modal.querySelector('.next-btn');
//         const slides = modal.querySelectorAll('.presentation-slide');
//         const slideCounter = modal.querySelector('.slide-counter');
//         let currentSlide = 0;
//         closeBtn.addEventListener('click', () => {
//             document.body.removeChild(modal);
//         });
//         prevBtn.addEventListener('click', () => {
//             slides[currentSlide].classList.remove('active');
//             currentSlide = (currentSlide - 1 + slides.length) % slides.length;
//             slides[currentSlide].classList.add('active');
//             slideCounter.textContent = `${currentSlide + 1} / ${slides.length}`;
//         });
//         nextBtn.addEventListener('click', () => {
//             slides[currentSlide].classList.remove('active');
//             currentSlide = (currentSlide + 1) % slides.length;
//             slides[currentSlide].classList.add('active');
//             slideCounter.textContent = `${currentSlide + 1} / ${slides.length}`;
//         });
//         document.addEventListener('keydown', function handleKeyPress(e) {
//             if (e.key === 'Escape') {
//                 document.body.removeChild(modal);
//                 document.removeEventListener('keydown', handleKeyPress);
//             } else if (e.key === 'ArrowLeft') {
//                 prevBtn.click();
//             } else if (e.key === 'ArrowRight') {
//                 nextBtn.click();
//             }
//         });
//     }
    
//     async function loadTemplates() {
//         try {
//             templatesGrid.innerHTML = `
//                 <div class="template-loading">
//                     <div class="spinner"></div>
//                     <p>Loading templates...</p>
//                 </div>
//             `;
//             const response = await fetch('/get_templates');
//             if (!response.ok) {
//                 throw new Error('Failed to load templates');
//             }
//             const data = await response.json();
//             templatesGrid.innerHTML = '';
//             if (Object.keys(data.templates).length === 0) {
//                 templatesGrid.innerHTML = `
//                     <div class="no-templates">
//                         <p>No templates available. Please check your template directory.</p>
//                     </div>
//                 `;
//                 return;
//             }
//             Object.entries(data.templates).forEach(([key, template]) => {
//                 const templateCard = document.createElement('div');
//                 templateCard.className = 'template-card';
//                 templateCard.dataset.templateId = key;
//                 templateCard.dataset.templateInfo = JSON.stringify(template);
//                 const hasPreviewImage = template.preview_image && template.preview_image.trim() !== '';
//                 templateCard.innerHTML = `
//                     <div class="template-image">
//                         ${hasPreviewImage ? 
//                             `<img src="${template.preview_image}" alt="${template.name}">` : 
//                             createTemplatePreview(template.styles)}
//                     </div>
//                     <div class="template-info">
//                         <h3>${template.name}</h3>
//                         <p>${template.description || 'No description available'}</p>
//                     </div>
//                 `;
//                 templateCard.addEventListener('click', function() {
//                     document.querySelectorAll('.template-card').forEach(card => {
//                         card.classList.remove('selected');
//                     });
//                     this.classList.add('selected');
//                     selectedTemplate = {
//                         id: key,
//                         ...template
//                     };
//                     selectedTemplateName.textContent = template.name;
//                     updateSelectedTemplatePreview(template);
//                 });
//                 templatesGrid.appendChild(templateCard);
//             });
            
//             function createTemplatePreview(styles) {
//                 const titleStyles = styles?.title_slide || {};
//                 const contentStyles = styles?.content_slide || {};
//                 let titleBg = '#ffffff';
//                 if (titleStyles.background?.type === 'solid') {
//                     const color = titleStyles.background.color || {r: 255, g: 255, b: 255};
//                     titleBg = `rgb(${color.r}, ${color.g}, ${color.b})`;
//                 } else if (titleStyles.background?.type === 'gradient') {
//                     const startColor = titleStyles.background.gradient_start || {r: 240, g: 240, b: 240};
//                     const endColor = titleStyles.background.gradient_end || {r: 200, g: 200, b: 200};
//                     titleBg = `linear-gradient(45deg, rgb(${startColor.r}, ${startColor.g}, ${startColor.b}), rgb(${endColor.r}, ${endColor.g}, ${endColor.b}))`;
//                 }
//                 let contentBg = '#ffffff';
//                 if (contentStyles.background?.type === 'solid') {
//                     const color = contentStyles.background.color || {r: 255, g: 255, b: 255};
//                     contentBg = `rgb(${color.r}, ${color.g}, ${color.b})`;
//                 } else if (contentStyles.background?.type === 'gradient') {
//                     const startColor = contentStyles.background.gradient_start || {r: 255, g: 255, b: 255};
//                     const endColor = contentStyles.background.gradient_end || {r: 200, g: 200, b: 200};
//                     contentBg = `linear-gradient(to bottom, rgb(${startColor.r}, ${startColor.g}, ${startColor.b}), rgb(${endColor.r}, ${endColor.g}, ${endColor.b}))`;
//                 }
//                 return `
//                     <div style="width: 100%; height: 100%; display: flex; flex-direction: column;">
//                         <div style="flex: 1; background: ${titleBg}; display: flex; justify-content: center; align-items: center;">
//                             <div style="width: 60%; height: 10px; background-color: #ddd; border-radius: 5px;"></div>
//                         </div>
//                         <div style="flex: 1; background: ${contentBg}; padding: 5px;">
//                             <div style="width: 40%; height: 5px; background-color: #ddd; margin-bottom: 5px; border-radius: 3px;"></div>
//                             <div style="width: 90%; height: 4px; background-color: #ddd; margin-bottom: 3px; border-radius: 2px;"></div>
//                             <div style="width: 85%; height: 4px; background-color: #ddd; margin-bottom: 3px; border-radius: 2px;"></div>
//                             <div style="width: 80%; height: 4px; background-color: #ddd; border-radius: 2px;"></div>
//                         </div>
//                     </div>
//                 `;
//             }
            
//             if (templatesGrid.children.length > 0) {
//                 templatesGrid.children[0].click();
//             }
//         } catch (error) {
//             console.error('Error loading templates:', error);
//             templatesGrid.innerHTML = `
//                 <div class="template-error">
//                     <p>Error loading templates: ${error.message}</p>
//                     <button id="retry-templates" class="btn">Retry</button>
//                 </div>
//             `;
//             document.getElementById('retry-templates')?.addEventListener('click', loadTemplates);
//         }
//     }
    
//     function updateSelectedTemplatePreview(template) {
//         selectedTemplatePreview.innerHTML = '';
//         const previewVisual = document.createElement('div');
//         previewVisual.className = 'template-visual-preview';
//         const styles = template.styles || {};
//         const titleSlideStyles = styles.title_slide || {};
//         const contentSlideStyles = styles.content_slide || {};
//         const imageSlideStyles = styles.image_slide || {};
//         let titleBgStyle = '#ffffff';
//         if (titleSlideStyles.background?.type === 'solid') {
//             const color = titleSlideStyles.background.color || {r: 240, g: 240, b: 240};
//             titleBgStyle = `rgb(${color.r}, ${color.g}, ${color.b})`;
//         } else if (titleSlideStyles.background?.type === 'gradient') {
//             const startColor = titleSlideStyles.background.gradient_start || {r: 240, g: 240, b: 240};
//             const endColor = titleSlideStyles.background.gradient_end || {r: 200, g: 200, b: 200};
//             titleBgStyle = `linear-gradient(45deg, rgb(${startColor.r}, ${startColor.g}, ${startColor.b}), rgb(${endColor.r}, ${endColor.g}, ${endColor.b}))`;
//         }
//         let contentBgStyle = '#ffffff';
//         if (contentSlideStyles.background?.type === 'solid') {
//             const color = contentSlideStyles.background.color || {r: 255, g: 255, b: 255};
//             contentBgStyle = `rgb(${color.r}, ${color.g}, ${color.b})`;
//         } else if (contentSlideStyles.background?.type === 'gradient') {
//             const startColor = contentSlideStyles.background.gradient_start || {r: 255, g: 255, b: 255};
//             const endColor = contentSlideStyles.background.gradient_end || {r: 200, g: 200, b: 200};
//             contentBgStyle = `linear-gradient(to bottom, rgb(${startColor.r}, ${startColor.g}, ${startColor.b}), rgb(${endColor.r}, ${endColor.g}, ${endColor.b}))`;
//         }
//         const titleImagePosition = titleSlideStyles.image_position || {left: 2.5, top: 4.0, width: 5.0, height: 2.5};
//         const contentImagePosition = contentSlideStyles.image_position || {left: 6.0, top: 1.5, width: 3.5, height: 4.5};
//         previewVisual.innerHTML = `
//             <div class="template-preview-slide" style="
//                 background: ${titleBgStyle};
//                 padding: 15px;
//                 border-radius: 5px;
//                 margin-bottom: 10px;
//                 text-align: center;
//                 position: relative;
//             ">
//                 <h5 style="
//                     color: ${titleSlideStyles.title_font?.color ? 
//                     `rgb(${titleSlideStyles.title_font.color.r}, ${titleSlideStyles.title_font.color.g}, ${titleSlideStyles.title_font.color.b})` : '#000000'};
//                     font-family: ${titleSlideStyles.title_font?.name || 'inherit'};
//                     margin: 0;
//                 ">Title Slide</h5>
//                 <div class="image-placeholder" style="
//                     position: absolute;
//                     left: ${titleImagePosition.left * 10}px;
//                     top: ${titleImagePosition.top * 10}px;
//                     width: ${titleImagePosition.width * 10}px;
//                     height: ${titleImagePosition.height * 10}px;
//                     background-color: rgb(${imageSlideStyles.fill_color?.r || 245}, ${imageSlideStyles.fill_color?.g || 245}, ${imageSlideStyles.fill_color?.b || 245});
//                     border: ${imageSlideStyles.border_width || 1.5}px ${imageSlideStyles.border_style || 'dashed'} rgb(${imageSlideStyles.border_color?.r || 200}, ${imageSlideStyles.border_color?.g || 200}, ${imageSlideStyles.border_color?.b || 200});
//                     margin-top: 10px;
//                     padding: 10px;
//                     font-size: 0.8em;
//                 ">
//                     <div style="font-size: 16px;">🖼️</div>
//                     <p style="margin: 0;">Image placeholder</p>
//                 </div>
//             </div>
//             <div class="template-preview-slide" style="
//                 background: ${contentBgStyle};
//                 padding: 15px;
//                 border-radius: 5px;
//                 text-align: left;
//                 position: relative;
//             ">
//                 <h5 style="
//                     color: ${contentSlideStyles.title_font?.color ? 
//                     `rgb(${contentSlideStyles.title_font.color.r}, ${contentSlideStyles.title_font.color.g}, ${contentSlideStyles.title_font.color.b})` : '#000000'};
//                     font-family: ${contentSlideStyles.title_font?.name || 'inherit'};
//                     margin: 0 0 10px 0;
//                 ">Content Slide</h5>
//                 <ul style="
//                     margin: 0;
//                     padding-left: 20px;
//                     font-size: 0.8em;
//                     color: ${contentSlideStyles.body_font?.color ? 
//                     `rgb(${contentSlideStyles.body_font.color.r}, ${contentSlideStyles.body_font.color.g}, ${contentSlideStyles.body_font.color.b})` : '#333333'};
//                 ">
//                     <li>Bullet point 1</li>
//                     <li>Bullet point 2</li>
//                 </ul>
//                 <div class="image-placeholder" style="
//                     position: absolute;
//                     left: ${contentImagePosition.left * 10}px;
//                     top: ${contentImagePosition.top * 10}px;
//                     width: ${contentImagePosition.width * 10}px;
//                     height: ${contentImagePosition.height * 10}px;
//                     background-color: rgb(${imageSlideStyles.fill_color?.r || 245}, ${imageSlideStyles.fill_color?.g || 245}, ${imageSlideStyles.fill_color?.b || 245});
//                     border: ${imageSlideStyles.border_width || 1.5}px ${imageSlideStyles.border_style || 'dashed'} rgb(${imageSlideStyles.border_color?.r || 200}, ${imageSlideStyles.border_color?.g || 200}, ${imageSlideStyles.border_color?.b || 200});
//                     margin-top: 10px;
//                     padding: 10px;
//                     font-size: 0.8em;
//                 ">
//                     <div style="font-size: 16px;">🖼️</div>
//                     <p style="margin: 0;">Image placeholder</p>
//                 </div>
//             </div>
//         `;
//         selectedTemplatePreview.appendChild(previewVisual);
//     }
    
//     function generateEditor(content) {
//         const editorContainer = document.getElementById('editor-content');
//         editorContainer.innerHTML = '';
        
//         // Presentation Title
//         const titleEditor = document.createElement('div');
//         titleEditor.className = 'editor-item';
//         const titleLabel = document.createElement('label');
//         titleLabel.textContent = 'Presentation Title:';
//         titleEditor.appendChild(titleLabel);
//         const titleInput = document.createElement('input');
//         titleInput.type = 'text';
//         titleInput.className = 'form-control editor-title';
//         titleInput.value = content.title || '';
//         titleInput.id = 'edit-presentation-title';
//         titleEditor.appendChild(titleInput);
//         editorContainer.appendChild(titleEditor);
        
//         // Slides
//         content.slides.forEach((slide, slideIndex) => {
//             const slideEditor = document.createElement('div');
//             slideEditor.className = 'slide-editor';
//             const slideHeader = document.createElement('h3');
//             slideHeader.textContent = `Slide ${slideIndex + 1}`;
//             slideEditor.appendChild(slideHeader);
            
//             // Slide Title
//             const slideTitleLabel = document.createElement('label');
//             slideTitleLabel.textContent = 'Slide Title:';
//             const slideTitleInput = document.createElement('input');
//             slideTitleInput.type = 'text';
//             slideTitleInput.className = 'form-control';
//             slideTitleInput.value = slide.title || '';
//             slideTitleInput.id = `edit-slide-${slideIndex}-title`;
//             slideEditor.appendChild(slideTitleLabel);
//             slideEditor.appendChild(slideTitleInput);
            
//             // Slide Points
//             const pointsContainer = document.createElement('div');
//             pointsContainer.className = 'points-editor';
//             slide.points.forEach((point, pointIndex) => {
//                 const pointEditor = document.createElement('div');
//                 pointEditor.className = 'point-editor';
//                 const pointLabel = document.createElement('label');
//                 pointLabel.textContent = `Point ${pointIndex + 1}:`;
//                 const pointInput = document.createElement('textarea');
//                 pointInput.className = 'form-control';
//                 pointInput.value = point || '';
//                 pointInput.id = `edit-slide-${slideIndex}-point-${pointIndex}`;
//                 pointInput.rows = 2;
//                 pointEditor.appendChild(pointLabel);
//                 pointEditor.appendChild(pointInput);
//                 pointsContainer.appendChild(pointEditor);
//             });
//             slideEditor.appendChild(pointsContainer);
            
//             // Image Prompt (Read-only)
//             const imagePromptKey = slideIndex.toString();
//             if (presentationData.image_prompts && presentationData.image_prompts[imagePromptKey]) {
//                 const imagePromptEditor = document.createElement('div');
//                 imagePromptEditor.className = 'image-prompt-editor';
//                 const imagePromptLabel = document.createElement('label');
//                 imagePromptLabel.textContent = 'Image Prompt:';
//                 const imagePromptInput = document.createElement('textarea');
//                 imagePromptInput.className = 'form-control';
//                 imagePromptInput.value = presentationData.image_prompts[imagePromptKey];
//                 imagePromptInput.readOnly = true;
//                 imagePromptInput.rows = 2;
//                 imagePromptEditor.appendChild(imagePromptLabel);
//                 imagePromptEditor.appendChild(imagePromptInput);
//                 slideEditor.appendChild(imagePromptEditor);
//             }
            
//             editorContainer.appendChild(slideEditor);
//         });
//     }
    
//     editBtn.addEventListener('click', function() {
//         if (!presentationData || !presentationData.content) {
//             showError('No presentation data available for editing');
//             return;
//         }
//         previewSection.classList.add('hidden');
//         generateEditor(presentationData.content);
//         editorSection.classList.remove('hidden');
//     });
    
//     saveChangesBtn.addEventListener('click', async function() {
//         if (!presentationData) {
//             showError('No presentation data available');
//             return;
//         }
//         const updatedContent = {
//             title: document.getElementById('edit-presentation-title').value.trim(),
//             slides: []
//         };
        
//         // Collect slide data
//         const slideEditors = document.querySelectorAll('.slide-editor');
//         slideEditors.forEach((slideEditor, slideIndex) => {
//             const slideTitle = document.getElementById(`edit-slide-${slideIndex}-title`).value.trim();
//             const points = [];
//             const pointInputs = slideEditor.querySelectorAll('.point-editor textarea');
//             pointInputs.forEach((input) => {
//                 const pointText = input.value.trim();
//                 if (pointText) {
//                     points.push(pointText);
//                 }
//             });
//             updatedContent.slides.push({
//                 title: slideTitle || `Slide ${slideIndex + 1}`,
//                 points: points
//             });
//         });
        
//         if (!updatedContent.title) {
//             showError('Presentation title cannot be empty');
//             return;
//         }
//         if (updatedContent.slides.length === 0) {
//             showError('At least one slide is required');
//             return;
//         }
        
//         try {
//             editorSection.classList.add('hidden');
//             loadingSection.classList.remove('hidden');
//             updateStatus('Updating presentation...');
//             const response = await fetch('/update_ppt', {
//                 method: 'POST',
//                 headers: {
//                     'Content-Type': 'application/json',
//                 },
//                 body: JSON.stringify({
//                     content: updatedContent,
//                     image_prompts: presentationData.image_prompts,
//                     template: presentationData.template
//                 })
//             });
//             if (!response.ok) {
//                 const errorData = await response.json();
//                 throw new Error(errorData.error || 'Failed to update presentation');
//             }
//             const data = await response.json();
//             presentationData = {
//                 ...presentationData,
//                 content: updatedContent,
//                 preview_data: data.preview_data,
//                 download_url: data.download_url,
//                 filename: data.filename
//             };
//             generateHtmlPreview(presentationData.preview_data);
//             downloadLink.href = data.download_url;
//             downloadLink.setAttribute('download', data.filename);
//             loadingSection.classList.add('hidden');
//             previewSection.classList.remove('hidden');
//             updateStatus('Presentation updated successfully!');
//         } catch (error) {
//             console.error('Error updating presentation:', error);
//             showError(error.message || 'Failed to update presentation');
//             editorSection.classList.remove('hidden');
//             loadingSection.classList.add('hidden');
//         }
//     });
    
//     cancelEditBtn.addEventListener('click', function() {
//         editorSection.classList.add('hidden');
//         previewSection.classList.remove('hidden');
//     });
    
//     downloadBtn.addEventListener('click', function() {
//         if (presentationData && presentationData.download_url) {
//             window.location.href = presentationData.download_url;
//         }
//     });

//     presentationPreviewBtn.addEventListener('click', function() {
//         openFullScreenPreview();
//     });
    
//     tryAgainBtn.addEventListener('click', function() {
//         errorSection.classList.add('hidden');
//         contentFormSection.classList.remove('hidden');
//     });
    
//     function cycleStatusMessages() {
//         currentStatusIndex = (currentStatusIndex + 1) % statusMessages.length;
//         updateStatus(statusMessages[currentStatusIndex]);
//     }
    
//     function updateStatus(message) {
//         statusMessage.textContent = message;
//     }
    
//     function showError(message) {
//         errorMessage.textContent = message;
//         errorSection.classList.remove('hidden');
//         loadingSection.classList.add('hidden');
//         previewSection.classList.add('hidden');
//         editorSection.classList.add('hidden');
//     }
// });