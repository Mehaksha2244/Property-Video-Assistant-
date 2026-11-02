const form = document.querySelector('#listing-form');
const images = document.querySelector('#images');
const imageCount = document.querySelector('#image-count');
const preview = document.querySelector('#preview');
const previewContent = document.querySelector('#preview-content');
const toast = document.querySelector('#toast');

const tell = (message) => {
  toast.textContent = message;
  toast.classList.add('show');
  setTimeout(() => toast.classList.remove('show'), 4500);
};

images.addEventListener('change', () => {
  imageCount.textContent = `${images.files.length} image${images.files.length === 1 ? '' : 's'} selected`;
});

function listing() {
  const data = new FormData(form);
  return {
    property_name: data.get('property_name'),
    location: data.get('location'),
    price: data.get('price'),
    property_type: data.get('property_type'),
    features: String(data.get('features')).split(',').map(x => x.trim()).filter(Boolean),
    cta: data.get('cta'),
  };
}

function validDetails() {
  return form.reportValidity() && listing().features.length > 0;
}

function display(data) {
  previewContent.className = '';
  const captionHtml = `
    <p class="eyebrow">FACT-SAFE SCENE PLAN</p>
    <h2>${data.ai_available ? 'AI-assisted outline' : 'Template outline'}</h2>
    ${data.ai_intro ? `<p class="ai-note">${data.ai_intro}</p>` : ''}
    <ol class="caption-list">${data.captions.map(c => `<li>${c}</li>`).join('')}</ol>
  `;
  const videoHtml = data.download_url
    ? `<video class="video-player" src="${data.download_url}" controls></video>`
    : '';
  previewContent.innerHTML = captionHtml + videoHtml;
}

preview.addEventListener('click', async () => {
  if (!validDetails()) return;
  preview.disabled = true;
  preview.textContent = 'Preparing…';
  try {
    const response = await fetch('/api/preview-script', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(listing()),
    });
    const data = await response.json();
    if (!response.ok) throw Error(data.detail || 'Could not create preview.');
    display(data);
  } catch (error) {
    tell(error.message);
  } finally {
    preview.disabled = false;
    preview.textContent = 'Preview script';
  }
});

form.addEventListener('submit', async (event) => {
  event.preventDefault();
  if (!validDetails()) return;
  if (images.files.length < 4 || images.files.length > 8) {
    return tell('Please upload between 4 and 8 images.');
  }
  const button = form.querySelector('.generate');
  button.disabled = true;
  button.querySelector('span').textContent = 'Rendering video…';
  try {
    const response = await fetch('/api/render', {
      method: 'POST',
      body: new FormData(form),
    });
    const data = await response.json();
    if (!response.ok) throw Error(data.detail || 'The video could not be generated.');
    display(data);
    const link = document.createElement('a');
    link.href = data.download_url;
    link.download = 'property-video.mp4';
    link.click();
    tell('Your MP4 is ready. The download has started.');
  } catch (error) {
    tell(error.message);
  } finally {
    button.disabled = false;
    button.querySelector('span').textContent = 'Generate video';
  }
});
