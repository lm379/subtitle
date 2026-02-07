import * as cheerio from 'cheerio';

// Comment type definition
interface Comment {
  timestamp: number;
  color: number;
  row: number;
  content: string;
  type: number; // 0: right to left, 1: top, 2: bottom, 3: left to right
  size: number;
  height: number;
  length: number;
}

interface PositionedComment {
  timestamp: number;
  color: number;
  row: number;
  content: string;
  type: 'bilipos';
  size: number;
  height: number;
  length: number;
}

// Safe list class for safe indexing
class SafeList extends Array<any> {
  get(index: number, defaultValue: any = null): any {
    try {
      return this[index];
    } catch {
      return defaultValue;
    }
  }
}

// Helper functions
function ASSEscape(s: string): string {
  const ReplaceLeadingSpace = (s: string): string => {
    const sstrip = s.trim();
    const slen = s.length;
    if (slen === sstrip.length) return s;
    const llen = slen - s.trimStart().length;
    const rlen = slen - s.trimEnd().length;
    return '\u2007'.repeat(llen) + sstrip + '\u2007'.repeat(rlen);
  };
  
  return s
    .replace(/\\/g, '\\\\')
    .replace(/{/g, '\\{')
    .replace(/}/g, '\\}')
    .split('\n')
    .map(i => ReplaceLeadingSpace(i) || ' ')
    .join('\\N');
}

function CalculateLength(s: string): number {
  return Math.max(...s.split('\n').map(l => l.length));
}

function ConvertTimestamp(timestamp: number): string {
  const t = Math.round(timestamp * 100);
  const hour = Math.floor(t / 360000);
  const minute = Math.floor((t % 360000) / 6000);
  const second = Math.floor((t % 6000) / 100);
  const centisecond = t % 100;
  return `${hour}:${minute.toString().padStart(2, '0')}:${second.toString().padStart(2, '0')}.${centisecond.toString().padStart(2, '0')}`;
}

function ConvertColor(RGB: number, width = 1280, height = 576): string {
  if (RGB === 0x000000) return '000000';
  if (RGB === 0xffffff) return 'FFFFFF';
  
  const R = (RGB >> 16) & 0xff;
  const G = (RGB >> 8) & 0xff;
  const B = RGB & 0xff;
  
  if (width < 1280 && height < 576) {
    return `${B.toString(16).padStart(2, '0').toUpperCase()}${G.toString(16).padStart(2, '0').toUpperCase()}${R.toString(16).padStart(2, '0').toUpperCase()}`;
  }
  
  // Convert to BT.709
  const ClipByte = (x: number): number => {
    if (x > 255) return 255;
    if (x < 0) return 0;
    return Math.round(x);
  };
  
  const B2 = ClipByte(R * 0.00956384088080656 + G * 0.03217254540203729 + B * 0.95826361371715607);
  const G2 = ClipByte(R * -0.1049393314207539 + G * 1.17231478191855154 + B * -0.06737545049779757);
  const R2 = ClipByte(R * 0.91348912373987645 + G * 0.0785853637253251 + B * 0.00792551253479842);
  
  return `${B2.toString(16).padStart(2, '0').toUpperCase()}${G2.toString(16).padStart(2, '0').toUpperCase()}${R2.toString(16).padStart(2, '0').toUpperCase()}`;
}

function ConvertType2(row: number, height: number, bottomReserved: number): number {
  return height - bottomReserved - row;
}

// Result: (f, dx, dy)
// To convert: NewX = f*x+dx, NewY = f*y+dy
function GetZoomFactor(SourceSize: [number, number], TargetSize: [number, number]): [number, number, number] {
  const SourceAspect = SourceSize[0] / SourceSize[1];
  const TargetAspect = TargetSize[0] / TargetSize[1];
  let ScaleFactor: number;
  let Cached_Result: [number, number, number];

  if (TargetAspect < SourceAspect) {  // narrower
    ScaleFactor = TargetSize[0] / SourceSize[0];
    Cached_Result = [ScaleFactor, 0, (TargetSize[1] - TargetSize[0] / SourceAspect) / 2];
  } else if (TargetAspect > SourceAspect) {  // wider
    ScaleFactor = TargetSize[1] / SourceSize[1];
    Cached_Result = [ScaleFactor, (TargetSize[0] - TargetSize[1] * SourceAspect) / 2, 0];
  } else {
    Cached_Result = [TargetSize[0] / SourceSize[0], 0, 0];
  }

  return Cached_Result;
}

// Calculation is based on https://github.com/jabbany/CommentCoreLibrary/issues/5#issuecomment-40087282
//                     and https://github.com/m13253/danmaku2ass/issues/7#issuecomment-41489422
// ASS FOV = width*4/3.0
// But Flash FOV = width/math.tan(100*math.pi/360.0)/2 will be used instead
// Result: (transX, transY, rotX, rotY, rotZ, scaleX, scaleY)
function ConvertFlashRotation(rotY: number, rotZ: number, X: number, Y: number, width: number, height: number): [number, number, number, number, number, number, number] {
  const WrapAngle = (deg: number): number => {
    return 180 - ((180 - deg) % 360);
  };
  
  rotY = WrapAngle(rotY);
  rotZ = WrapAngle(rotZ);
  
  if (rotY === 90 || rotY === -90) {
    rotY -= 1;
  }
  
  let outX: number, outY: number, outZ: number;
  
  if (rotY === 0 || rotZ === 0) {
    outX = 0;
    outY = -rotY;  // Positive value means clockwise in Flash
    outZ = -rotZ;
    rotY *= Math.PI / 180.0;
    rotZ *= Math.PI / 180.0;
  } else {
    rotY *= Math.PI / 180.0;
    rotZ *= Math.PI / 180.0;
    outY = Math.atan2(-Math.sin(rotY) * Math.cos(rotZ), Math.cos(rotY)) * 180 / Math.PI;
    outZ = Math.atan2(-Math.cos(rotY) * Math.sin(rotZ), Math.cos(rotZ)) * 180 / Math.PI;
    outX = Math.asin(Math.sin(rotY) * Math.sin(rotZ)) * 180 / Math.PI;
  }
  
  let trX = (X * Math.cos(rotZ) + Y * Math.sin(rotZ)) / Math.cos(rotY) + (1 - Math.cos(rotZ) / Math.cos(rotY)) * width / 2 - Math.sin(rotZ) / Math.cos(rotY) * height / 2;
  let trY = Y * Math.cos(rotZ) - X * Math.sin(rotZ) + Math.sin(rotZ) * width / 2 + (1 - Math.cos(rotZ)) * height / 2;
  const trZ = (trX - width / 2) * Math.sin(rotY);
  const FOV = width * Math.tan(2 * Math.PI / 9.0) / 2;
  let scaleXY = FOV / (FOV + trZ);
  
  if (scaleXY < 0) {
    scaleXY = -scaleXY;
    outX += 180;
    outY += 180;
  }
  
  trX = (trX - width / 2) * scaleXY + width / 2;
  trY = (trY - height / 2) * scaleXY + height / 2;
  
  return [trX, trY, WrapAngle(outX), WrapAngle(outY), WrapAngle(outZ), scaleXY * 100, scaleXY * 100];
}

// Fetch Bilibili comments - Version 1.0
function ReadCommentsBilibili1(xmlStr: string, fontsize: number): (Comment | PositionedComment)[] {
  const $ = cheerio.load(xmlStr, { xmlMode: true });
  const comments: (Comment | PositionedComment)[] = [];
  let index = 0;
  
  $('d').each((_, element) => {
    const $el = $(element);
    const p = $el.attr('p');
    
    if (!p) return;
    
    const parts = p.split(',');
    
    try {
      if (parts.length >= 5 && ['1', '4', '5', '6', '7', '8'].includes(parts[1])) {
        const content = $el.text().replace('/n', '\n');
        
        if (['1', '4', '5', '6'].includes(parts[1])) {
          const timestamp = parseFloat(parts[0]);
          const color = parseInt(parts[3]);
          const row = parseInt(parts[4]);
          const typeMap: Record<string, number> = { '1': 0, '4': 2, '5': 1, '6': 3 };
          const size = parseInt(parts[2]) * fontsize / 25.0;
          const height = (content.split('\n').length) * size;
          const length = CalculateLength(content) * size;
          
          comments.push({
            timestamp,
            color,
            row,
            content,
            type: typeMap[parts[1]],
            size,
            height,
            length
          });
        } else if (parts[1] === '7') {
          const timestamp = parseFloat(parts[0]);
          const color = parseInt(parts[3]);
          const row = parseInt(parts[4]);
          const size = parseInt(parts[2]);
          
          comments.push({
            timestamp,
            color,
            row,
            content,
            type: 'bilipos',
            size,
            height: 0,
            length: 0
          });
        }
      }
    } catch (error) {
      console.error('Error parsing comment:', error);
    }
    
    index++;
  });
  
  return comments;
}

// Fetch Bilibili comments - Version 2.0
function ReadCommentsBilibili2(xmlStr: string, fontsize: number): (Comment | PositionedComment)[] {
  const $ = cheerio.load(xmlStr, { xmlMode: true });
  const comments: (Comment | PositionedComment)[] = [];
  let index = 0;
  
  $('d').each((_, element) => {
    const $el = $(element);
    const p = $el.attr('p');
    
    if (!p) return;
    
    const parts = p.split(',');
    
    try {
      if (parts.length >= 7 && ['1', '4', '5', '6', '7', '8'].includes(parts[3])) {
        const content = $el.text().replace('/n', '\n');
        const timestamp = parseFloat(parts[2]) / 1000.0;
        
        if (['1', '4', '5', '6'].includes(parts[3])) {
          const color = parseInt(parts[5]);
          const row = parseInt(parts[6]);
          const typeMap: Record<string, number> = { '1': 0, '4': 2, '5': 1, '6': 3 };
          const size = parseInt(parts[4]) * fontsize / 25.0;
          const height = (content.split('\n').length) * size;
          const length = CalculateLength(content) * size;
          
          comments.push({
            timestamp,
            color,
            row,
            content,
            type: typeMap[parts[3]],
            size,
            height,
            length
          });
        } else if (parts[3] === '7') {
          const color = parseInt(parts[5]);
          const row = parseInt(parts[6]);
          const size = parseInt(parts[4]);
          
          comments.push({
            timestamp,
            color,
            row,
            content,
            type: 'bilipos',
            size,
            height: 0,
            length: 0
          });
        }
      }
    } catch (error) {
      console.error('Error parsing comment:', error);
    }
    
    index++;
  });
  
  return comments;
}

// Fetch all Bilibili comments
async function getComments(cid: string, fontsize = 25): Promise<(Comment | PositionedComment)[]> {
  const headers = {
    "Accept": "*/*",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36 Edg/144.0.0.0"
  };
  
  const resp = await fetch(`https://comment.bilibili.com/${cid}.xml`, { headers });
  const text = await resp.text();
  
  let comments: (Comment | PositionedComment)[] = [];
  
  if (text.includes('<?xml version="1.0"')) {
    comments = ReadCommentsBilibili1(text, fontsize);
  } else if (text.includes('<?xml version="2.0"')) {
    comments = ReadCommentsBilibili2(text, fontsize);
  }
  
  comments.sort((a, b) => a.timestamp - b.timestamp);
  return comments;
}

// Write positioned comment (B站特有定位弹幕)
function WriteCommentBilibiliPositioned(
  comment: PositionedComment,
  width: number,
  height: number,
  styleId: string,
  contents: string[]
): void {
  // BiliPlayerSize = (512, 384)  # Bilibili player version 2010
  // BiliPlayerSize = (540, 384)  # Bilibili player version 2012
  const BiliPlayerSize: [number, number] = [672, 438];  // Bilibili player version 2014
  const ZoomFactor = GetZoomFactor(BiliPlayerSize, [width, height]);

  const GetPosition = (InputPos: any, isHeight: boolean): number => {
    const isHeightInt = Number(isHeight);  // True -> 1
    if (typeof InputPos === 'number') {
      if (Number.isInteger(InputPos)) {
        return ZoomFactor[0] * InputPos + ZoomFactor[isHeightInt + 1];
      } else {
        if (InputPos > 1) {
          return ZoomFactor[0] * InputPos + ZoomFactor[isHeightInt + 1];
        } else {
          return BiliPlayerSize[isHeightInt] * ZoomFactor[0] * InputPos + ZoomFactor[isHeightInt + 1];
        }
      }
    } else {
      try {
        InputPos = parseInt(InputPos);
      } catch {
        InputPos = parseFloat(InputPos);
      }
      return GetPosition(InputPos, isHeight);
    }
  };

  try {
    const commentArgs = new SafeList(JSON.parse(comment.content));
    const text = ASSEscape(String(commentArgs.get(4)).replace('/n', '\n'));
    
    let from_x = commentArgs.get(0, 0);
    let from_y = commentArgs.get(1, 0);
    let to_x = commentArgs.get(7, from_x);
    let to_y = commentArgs.get(8, from_y);
    
    from_x = GetPosition(from_x, false);
    from_y = GetPosition(from_y, true);
    to_x = GetPosition(to_x, false);
    to_y = GetPosition(to_y, true);
    
    const alphaStr = String(commentArgs.get(2, '1')).split('-');
    const alphaList = new SafeList(alphaStr);
    let from_alpha = parseFloat(alphaList.get(0, '1'));
    const to_alpha = parseFloat(alphaList.get(1, from_alpha));
    
    from_alpha = 255 - Math.round(from_alpha * 255);
    const to_alpha_final = 255 - Math.round(to_alpha * 255);
    
    const rotate_z = parseInt(commentArgs.get(5, '0'));
    const rotate_y = parseInt(commentArgs.get(6, '0'));
    const lifetime = parseFloat(commentArgs.get(3, '4500'));
    const duration = parseInt(commentArgs.get(9, (lifetime * 1000).toString()));
    const delay = parseInt(commentArgs.get(10, '0'));
    const fontface = commentArgs.get(12, '');
    const isborder = commentArgs.get(11, 'true');
    
    const from_rotarg = ConvertFlashRotation(rotate_y, rotate_z, from_x, from_y, width, height);
    const to_rotarg = ConvertFlashRotation(rotate_y, rotate_z, to_x, to_y, width, height);
    
    const styles: string[] = [`\\org(${width / 2}, ${height / 2})`];
    
    if (from_rotarg[0] === to_rotarg[0] && from_rotarg[1] === to_rotarg[1]) {
      styles.push(`\\pos(${from_rotarg[0].toFixed(0)}, ${from_rotarg[1].toFixed(0)})`);
    } else {
      styles.push(`\\move(${from_rotarg[0].toFixed(0)}, ${from_rotarg[1].toFixed(0)}, ${to_rotarg[0].toFixed(0)}, ${to_rotarg[1].toFixed(0)}, ${delay}, ${delay + duration})`);
    }
    
    styles.push(`\\frx${from_rotarg[2].toFixed(0)}\\fry${from_rotarg[3].toFixed(0)}\\frz${from_rotarg[4].toFixed(0)}\\fscx${from_rotarg[5].toFixed(0)}\\fscy${from_rotarg[6].toFixed(0)}`);
    
    if (from_x !== to_x || from_y !== to_y) {
      styles.push(`\\t(${delay}, ${delay + duration}, `);
      styles.push(`\\frx${to_rotarg[2].toFixed(0)}\\fry${to_rotarg[3].toFixed(0)}\\frz${to_rotarg[4].toFixed(0)}\\fscx${to_rotarg[5].toFixed(0)}\\fscy${to_rotarg[6].toFixed(0)}`);
      styles.push(')');
    }
    
    if (fontface) {
      styles.push(`\\fn${ASSEscape(fontface)}`);
    }
    
    styles.push(`\\fs${(comment.size * ZoomFactor[0]).toFixed(0)}`);
    
    if (comment.color !== 0xffffff) {
      styles.push(`\\c&H${ConvertColor(comment.color)}&`);
      if (comment.color === 0x000000) {
        styles.push('\\3c&HFFFFFF&');
      }
    }
    
    if (from_alpha === to_alpha_final) {
      styles.push(`\\alpha&H${from_alpha.toString(16).padStart(2, '0').toUpperCase()}`);
    } else if (from_alpha === 255 && to_alpha_final === 0) {
      styles.push(`\\fad(${(lifetime * 1000).toFixed(0)},0)`);
    } else if (from_alpha === 0 && to_alpha_final === 255) {
      styles.push(`\\fad(0,${(lifetime * 1000).toFixed(0)})`);
    } else {
      styles.push(`\\fade(${from_alpha}, ${to_alpha_final}, ${to_alpha_final}, 0, ${(lifetime * 1000).toFixed(0)}, ${(lifetime * 1000).toFixed(0)}, ${(lifetime * 1000).toFixed(0)})`);
    }
    
    if (isborder === 'false') {
      styles.push('\\bord0');
    }
    
    contents.push(`Dialogue: -1,${ConvertTimestamp(comment.timestamp)},${ConvertTimestamp(comment.timestamp + lifetime)},${styleId},,0,0,0,,{${styles.join('')}}${text}\n`);
  } catch (e) {
    console.error('Error processing positioned comment:', e);
  }
}

// Write ASS header
function WriteASSHead(
  width: number,
  height: number,
  fontface: string,
  fontsize: number,
  alpha: number,
  styleId: string,
  contents: string[]
): void {
  const alphaValue = (255 - Math.round(alpha * 255)).toString(16).padStart(2, '0').toUpperCase();
  contents.push(`[Script Info]
; Script generated by Danmaku2ASS
; https://github.com/m13253/danmaku2ass
Script Updated By: Danmaku2ASS (https://github.com/m13253/danmaku2ass)
ScriptType: v4.00+
PlayResX: ${width}
PlayResY: ${height}
Aspect Ratio: ${width}:${height}
Collisions: Normal
WrapStyle: 2
ScaledBorderAndShadow: yes
YCbCr Matrix: TV.601
[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: ${styleId}, ${fontface}, ${fontsize.toFixed(0)}, &H${alphaValue}FFFFFF, &H${alphaValue}FFFFFF, &H${alphaValue}000000, &H${alphaValue}000000, 1, 0, 0, 0, 100, 100, 0.00, 0.00, 1, ${Math.max(fontsize / 25.0, 1).toFixed(0)}, 0, 7, 0, 0, 0, 0
[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
`);
}

// Write regular comment
function WriteComment(
  comment: Comment,
  row: number,
  width: number,
  height: number,
  bottomReserved: number,
  fontsize: number,
  duration_marquee: number,
  duration_still: number,
  styleId: string,
  contents: string[]
): void {
  const text = ASSEscape(comment.content);
  const styles: string[] = [];
  let duration: number;
  
  if (comment.type === 1) {
    // Top
    styles.push(`\\an8\\pos(${width / 2}, ${row})`);
    duration = duration_still;
  } else if (comment.type === 2) {
    // Bottom
    styles.push(`\\an2\\pos(${width / 2}, ${ConvertType2(row, height, bottomReserved)})`);
    duration = duration_still;
  } else if (comment.type === 3) {
    // Left to right
    styles.push(`\\move(${-Math.ceil(comment.length)}, ${row}, ${width}, ${row})`);
    duration = duration_marquee;
  } else {
    // Right to left
    styles.push(`\\move(${width}, ${row}, ${-Math.ceil(comment.length)}, ${row})`);
    duration = duration_marquee;
  }
  
  if (!(comment.size > fontsize - 1 && comment.size < fontsize + 1)) {
    styles.push(`\\fs${comment.size.toFixed(0)}`);
  }
  
  if (comment.color !== 0xffffff) {
    styles.push(`\\c&H${ConvertColor(comment.color)}&`);
    if (comment.color === 0x000000) {
      styles.push('\\3c&HFFFFFF&');
    }
  }
  
  contents.push(`Dialogue: 2,${ConvertTimestamp(comment.timestamp)},${ConvertTimestamp(comment.timestamp + duration)},${styleId},,0000,0000,0000,,{${styles.join('')}}${text}\n`);
}

// Test if rows are free
function TestFreeRows(
  rows: (Comment | PositionedComment | null)[][],
  comment: Comment | PositionedComment,
  row: number,
  width: number,
  height: number,
  bottomReserved: number,
  duration_marquee: number,
  duration_still: number
): number {
  const rowmax = height - bottomReserved;
  let targetRow: Comment | PositionedComment | null = null;
  let res = 0;
  
  if (typeof comment.type === 'number' && (comment.type === 1 || comment.type === 2)) {
    // Top or bottom still
    while (row < rowmax && res < comment.height) {
      if (targetRow !== rows[comment.type][row]) {
        targetRow = rows[comment.type][row];
        if (targetRow && targetRow.timestamp + duration_still > comment.timestamp) {
          break;
        }
      }
      row++;
      res++;
    }
  } else if (typeof comment.type === 'number') {
    // Scrolling
    let thresholdTime: number;
    try {
      thresholdTime = comment.timestamp - duration_marquee * (1 - width / (comment.length + width));
    } catch {
      thresholdTime = comment.timestamp - duration_marquee;
    }
    
    while (row < rowmax && res < comment.height) {
      if (targetRow !== rows[comment.type][row]) {
        targetRow = rows[comment.type][row];
        if (targetRow) {
          try {
            if (targetRow.timestamp > thresholdTime ||
                targetRow.timestamp + targetRow.length * duration_marquee / (targetRow.length + width) > comment.timestamp) {
              break;
            }
          } catch {
            // Ignore
          }
        }
      }
      row++;
      res++;
    }
  }
  
  return res;
}

// Find alternative row when screen is full
function FindAlternativeRow(
  rows: (Comment | PositionedComment | null)[][],
  comment: Comment,
  height: number,
  bottomReserved: number
): number {
  let res = 0;
  for (let row = 0; row < height - bottomReserved - Math.ceil(comment.height); row++) {
    if (!rows[comment.type][row]) return row;
    const rowComment = rows[comment.type][row];
    const resComment = rows[comment.type][res];
    if (rowComment && resComment && rowComment.timestamp < resComment.timestamp) {
      res = row;
    }
  }
  return res;
}

// Mark comment row as used
function MarkCommentRow(
  rows: (Comment | PositionedComment | null)[][],
  comment: Comment | PositionedComment,
  row: number
): void {
  if (typeof comment.type === 'number') {
    for (let i = row; i < row + Math.ceil(comment.height); i++) {
      try {
        rows[comment.type][i] = comment;
      } catch {
        // Ignore index out of bounds
      }
    }
  }
}

// Process all comments and generate ASS format
function ProcessComments(
  comments: (Comment | PositionedComment)[],
  width: number,
  height: number,
  bottomReserved: number,
  fontface: string,
  fontsize: number,
  alpha: number,
  duration_marquee: number,
  duration_still: number,
  filters: RegExp[],
  is_reduce_comments: boolean,
  contents: string[]
): void {
  const styleId = `Danmaku2ASS_${Math.floor(Math.random() * 0x10000).toString(16).padStart(4, '0')}`;
  
  WriteASSHead(width, height, fontface, fontsize, alpha, styleId, contents);
  
  // Track used rows
  const rows: (Comment | PositionedComment | null)[][] = [[], [], [], []];
  for (let i = 0; i < 4; i++) {
    rows[i] = Array(height - bottomReserved + 1).fill(null);
  }
  
  comments.forEach((comment) => {
    // Filter comments
    if (typeof comment.type === 'number' && filters.length > 0) {
      for (const filter of filters) {
        if (filter.test(comment.content)) return;
      }
    }
    
    // Handle positioned comments
    if (comment.type === 'bilipos') {
      WriteCommentBilibiliPositioned(comment, width, height, styleId, contents);
      return;
    }
    
    // Regular comment processing
    const rowmax = height - bottomReserved - comment.height;
    let found = false;
    
    for (let row = 0; row < rowmax && !found; row++) {
      const freerows = TestFreeRows(rows, comment, row, width, height, bottomReserved, duration_marquee, duration_still);
      
      if (freerows >= comment.height) {
        MarkCommentRow(rows, comment, row);
        WriteComment(comment, row, width, height, bottomReserved, fontsize, duration_marquee, duration_still, styleId, contents);
        found = true;
      }
    }
    
    // Reduce comments if screen is full
    if (!found && !is_reduce_comments && typeof comment.type === 'number') {
      const row = FindAlternativeRow(rows, comment, height, bottomReserved);
      MarkCommentRow(rows, comment, row);
      WriteComment(comment, row, width, height, bottomReserved, fontsize, duration_marquee, duration_still, styleId, contents);
    }
  });
}

// Main export function
export async function xml2ass(
  cid: string,
  width = 1920,
  height = 1080,
  bottomReserved = 0,
  fontface = 'Microsoft YaHei',
  fontsize = 25.0,
  alpha = 1.0,
  duration_marquee = 5.0,
  duration_still = 5.0,
  filter: string | null = null,
  _filterFile: string | null = null,
  is_reduce_comments = false
): Promise<string> {
  const comments = await getComments(cid, fontsize);
  
  const filters: RegExp[] = [];
  if (filter) {
    try {
      filters.push(new RegExp(filter));
    } catch (e) {
      console.error('Invalid filter regex:', filter);
    }
  }
  
  const contents: string[] = [];
  ProcessComments(
    comments,
    width,
    height,
    bottomReserved,
    fontface,
    fontsize,
    alpha,
    duration_marquee,
    duration_still,
    filters,
    is_reduce_comments,
    contents
  );
  
  return contents.join('');
}
