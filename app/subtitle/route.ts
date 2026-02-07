import { NextRequest, NextResponse } from 'next/server';

// Helper function to parse query params or form data
function getValue(request: NextRequest, key: string): string {
  const urlParams = request.nextUrl.searchParams.get(key);
  if (urlParams) return urlParams;
  return '';
}

// Helper function to check if value is a float
function isFloat(x: any): boolean {
  try {
    float(x);
    return true;
  } catch {
    return false;
  }
}

function float(x: any): number {
  if (typeof x === 'number') return x;
  const parsed = parseFloat(x);
  if (isNaN(parsed)) throw new Error('Not a number');
  return parsed;
}

// Convert timestamp to SRT format
function gettime(t: number): string {
  t = Math.floor(t * 1000);
  const h = Math.floor(t / 3600000);
  t %= 3600000;
  const m = Math.floor(t / 60000);
  t %= 60000;
  const s = Math.floor(t / 1000);
  const ms = t % 1000;
  return `${h.toString().padStart(2, '0')}:${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')},${ms.toString().padStart(3, '0')}`;
}

// Convert JSON subtitle to SRT format
async function json2srt(url: string): Promise<string> {
  try {
    const resp = await fetch(url);
    const data = await resp.json();
    const body = data.body || [];
    let srt = '';
    for (let i = 0; i < body.length; i++) {
      const item = body[i];
      srt += `${i + 1}\n`;
      srt += `${gettime(item.from)} --> ${gettime(item.to)}\n`;
      srt += `${item.content}\n`;
    }
    return srt;
  } catch (error) {
    console.error('Error in json2srt:', error);
    return '';
  }
}

// Main subtitle handler
export async function GET(request: NextRequest) {
  const url = getValue(request, 'url');
  
  // If url is provided, generate SRT from JSON
  if (url) {
    const srt = await json2srt(url);
    return new NextResponse(srt, {
      status: 200,
      headers: { 'Content-Type': 'text/plain; charset=utf-8' },
    });
  }
  
  // Otherwise, generate ASS from Bilibili danmaku
  const cid = getValue(request, 'cid');
  if (!cid) {
    return new NextResponse('', {
      status: 200,
      headers: { 'Content-Type': 'text/plain; charset=utf-8' },
    });
  }
  
  const width = isFloat(getValue(request, 'width')) ? Math.floor(float(getValue(request, 'width'))) : 1920;
  const height = isFloat(getValue(request, 'height')) ? Math.floor(float(getValue(request, 'height'))) : 1080;
  const font = getValue(request, 'font') || 'Microsoft YaHei';
  const fontsize = isFloat(getValue(request, 'font_size')) ? float(getValue(request, 'font_size')) : 40.0;
  const alpha = isFloat(getValue(request, 'alpha')) ? float(getValue(request, 'alpha')) : 0.8;
  const duration_marquee = isFloat(getValue(request, 'duration_marquee')) ? float(getValue(request, 'duration_marquee')) : 15.0;
  const duration_still = isFloat(getValue(request, 'duration_still')) ? float(getValue(request, 'duration_still')) : 5.0;
  const is_reduce_comments = getValue(request, 'is_reduce_comments').toUpperCase() === 'TRUE';
  const display_area = isFloat(getValue(request, 'display_area')) ? float(getValue(request, 'display_area')) : 0.8;
  const protect = Math.floor((1.0 - display_area) * height);
  
  // Import the xml2ass function
  const { xml2ass } = await import('../../lib/xml2ass');
  
  const ass = await xml2ass(
    cid,
    width,
    height,
    protect,
    font,
    fontsize,
    alpha,
    duration_marquee,
    duration_still,
    null,
    null,
    is_reduce_comments
  );
  
  return new NextResponse(ass, {
    status: 200,
    headers: { 'Content-Type': 'text/plain; charset=utf-8' },
  });
}

export async function POST(request: NextRequest) {
  const formData = await request.formData();
  
  const url = formData.get('url') as string;
  
  // If url is provided, generate SRT from JSON
  if (url) {
    const srt = await json2srt(url);
    return new NextResponse(srt, {
      status: 200,
      headers: { 'Content-Type': 'text/plain; charset=utf-8' },
    });
  }
  
  // Otherwise, generate ASS from Bilibili danmaku
  const cid = formData.get('cid') as string;
  if (!cid) {
    return new NextResponse('', {
      status: 200,
      headers: { 'Content-Type': 'text/plain; charset=utf-8' },
    });
  }
  
  const width = isFloat(formData.get('width')) ? Math.floor(float(formData.get('width'))) : 1920;
  const height = isFloat(formData.get('height')) ? Math.floor(float(formData.get('height'))) : 1080;
  const font = (formData.get('font') as string) || 'Microsoft YaHei';
  const fontsize = isFloat(formData.get('font_size')) ? float(formData.get('font_size')) : 40.0;
  const alpha = isFloat(formData.get('alpha')) ? float(formData.get('alpha')) : 0.8;
  const duration_marquee = isFloat(formData.get('duration_marquee')) ? float(formData.get('duration_marquee')) : 15.0;
  const duration_still = isFloat(formData.get('duration_still')) ? float(formData.get('duration_still')) : 5.0;
  const is_reduce_comments = (formData.get('is_reduce_comments') as string).toUpperCase() === 'TRUE';
  const display_area = isFloat(formData.get('display_area')) ? float(formData.get('display_area')) : 0.8;
  const protect = Math.floor((1.0 - display_area) * height);
  
  // Import the xml2ass function
  const { xml2ass } = await import('../../lib/xml2ass');
  
  const ass = await xml2ass(
    cid,
    width,
    height,
    protect,
    font,
    fontsize,
    alpha,
    duration_marquee,
    duration_still,
    null,
    null,
    is_reduce_comments
  );
  
  return new NextResponse(ass, {
    status: 200,
    headers: { 'Content-Type': 'text/plain; charset=utf-8' },
  });
}
