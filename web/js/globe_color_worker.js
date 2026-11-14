// Prepare the unchanged NASA SVS colour JPEG away from camera/input rendering.
// The transferred RGBA buffer is already flipped to the globe texture's UVs.
self.onmessage = async ({ data: { url, maxSize } }) => {
  let bitmap;
  try {
    const response = await fetch(url);
    if (!response.ok) throw new Error(`Colour texture: ${response.status}`);
    bitmap = await createImageBitmap(await response.blob(), { colorSpaceConversion: 'none' });
    // Match Three's legacy image-size cap on GPUs unable to hold an 8K texture.
    const scale = Math.min(1, maxSize / Math.max(bitmap.width, bitmap.height));
    const width = Math.floor(bitmap.width * scale), height = Math.floor(bitmap.height * scale);
    const canvas = new OffscreenCanvas(width, height);
    const ctx = canvas.getContext('2d', { willReadFrequently: true });
    ctx.translate(0, height); ctx.scale(1, -1);
    ctx.drawImage(bitmap, 0, 0, width, height);
    const pixels = ctx.getImageData(0, 0, width, height).data.buffer;
    self.postMessage({ pixels, width, height }, [pixels]);
  } catch (error) {
    self.postMessage({ error: String(error) });
  } finally {
    bitmap?.close();
  }
};
