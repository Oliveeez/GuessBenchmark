#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
sequential_variant_generator.py

Sequential Structure Variant Generator: Generate multiple layout variations 
of emoji sequences on a plane with different arrangement patterns.
Integrates with EmojiProcessAgent for high-quality emoji fetching.
"""

import json
import os
import math
import regex
import argparse
from typing import List, Tuple, Dict, Optional
from PIL import Image, ImageDraw, ImageFont

try:
    from emoji_process_agent import EmojiProcessAgent
except ImportError:
    raise ImportError("EmojiProcessAgent not found. Please ensure emoji_process_agent.py is in the same directory.")



class LayoutEngine:
    """Layout engine for calculating emoji positions"""
    
    @staticmethod
    def calculate_positions(num_emojis: int, layout_type: str, canvas_size: Tuple[int, int], 
                          emoji_size: int, margin_ratio: float = 0.2) -> List[Tuple[float, float]]:
        """
        Calculate positions for emojis based on layout type
        
        Args:
            num_emojis: Number of emojis to position
            layout_type: Type of layout ('horizontal', 'vertical', 'diagonal', 'circular', 'grid', 'zigzag', 'star')
            canvas_size: Canvas dimensions (width, height)
            emoji_size: Size of each emoji
            margin_ratio: Margin as ratio of canvas size
            
        Returns:
            List of (x, y) positions - exactly num_emojis positions
        """
        width, height = canvas_size
        margin_x = int(width * margin_ratio)
        margin_y = int(height * margin_ratio)
        available_width = width - 2 * margin_x
        available_height = height - 2 * margin_y
        
        positions = []
        
        if layout_type == 'horizontal':
            y = height // 2
            if num_emojis == 1:
                positions.append((width // 2, y))
            else:
                for i in range(num_emojis):
                    x = margin_x + (available_width * i) / (num_emojis - 1)
                    positions.append((x, y))
        
        elif layout_type == 'vertical':
            x = width // 2
            if num_emojis == 1:
                positions.append((x, height // 2))
            else:
                for i in range(num_emojis):
                    y = margin_y + (available_height * i) / (num_emojis - 1)
                    positions.append((x, y))
        
        elif layout_type == 'diagonal':
            if num_emojis == 1:
                positions.append((width // 2, height // 2))
            else:
                for i in range(num_emojis):
                    factor = i / (num_emojis - 1)
                    x = margin_x + factor * available_width
                    y = margin_y + factor * available_height
                    positions.append((x, y))
        
        elif layout_type == 'circular':
            center_x, center_y = width // 2, height // 2
            if num_emojis == 1:
                positions.append((center_x, center_y))
            else:
                radius = min(available_width, available_height) // 3
                for i in range(num_emojis):
                    angle = 2 * math.pi * i / num_emojis - math.pi / 2  # Start from top
                    x = center_x + radius * math.cos(angle)
                    y = center_y + radius * math.sin(angle)
                    positions.append((x, y))
        
        elif layout_type == 'grid':
            cols = math.ceil(math.sqrt(num_emojis))
            rows = math.ceil(num_emojis / cols)
            
            for i in range(num_emojis):
                row = i // cols
                col = i % cols
                
                if cols == 1:
                    x = width // 2
                else:
                    x = margin_x + (available_width * col) / (cols - 1)
                
                if rows == 1:
                    y = height // 2
                else:
                    y = margin_y + (available_height * row) / (rows - 1)
                
                positions.append((x, y))
        
        elif layout_type == 'zigzag':
            if num_emojis <= 2:
                # For 1-2 emojis, use horizontal layout
                return LayoutEngine.calculate_positions(num_emojis, 'horizontal', canvas_size, emoji_size, margin_ratio)
            
            rows = 2
            cols = math.ceil(num_emojis / rows)
            
            for i in range(num_emojis):
                row = i // cols
                col = i % cols
                
                # Reverse direction for odd rows (zigzag effect)
                if row % 2 == 1:
                    col = cols - 1 - col
                
                if cols == 1:
                    x = width // 2
                else:
                    x = margin_x + (available_width * col) / (cols - 1)
                
                y = margin_y + (available_height * row) / (rows - 1)
                positions.append((x, y))
        
        elif layout_type == 'star':
            center_x, center_y = width // 2, height // 2
            if num_emojis == 1:
                positions.append((center_x, center_y))
            elif num_emojis == 2:
                # For 2 emojis, place them with some distance
                positions.append((center_x, center_y - emoji_size * 1.5))
                positions.append((center_x, center_y + emoji_size * 1.5))
            else:
                # Calculate radius to ensure emojis don't overlap with much larger spacing
                min_distance = emoji_size * 3.0  # Further increased minimum distance between emojis
                required_radius = min_distance / (2 * math.sin(math.pi / (num_emojis - 1)))
                
                # Use a radius that's at least the required radius but fits in canvas
                max_radius = min(available_width, available_height) // 2.2  # Increased from //2.5
                radius = max(required_radius, max_radius * 0.9)  # Increased from 0.8
                
                # Place first emoji at center
                positions.append((center_x, center_y))
                
                # Place remaining emojis in circle around center
                for i in range(1, num_emojis):
                    angle = 2 * math.pi * (i - 1) / (num_emojis - 1) - math.pi / 2
                    x = center_x + radius * math.cos(angle)
                    y = center_y + radius * math.sin(angle)
                    positions.append((x, y))
        
        # Ensure we return exactly num_emojis positions
        assert len(positions) == num_emojis, f"Expected {num_emojis} positions, got {len(positions)} for layout {layout_type}"
        
        return positions


class SequentialVariantGenerator:
    """Main class for generating sequential emoji layout variants"""
    
    # Available layout types
    LAYOUT_TYPES = ['horizontal', 'vertical', 'diagonal', 'circular', 'grid', 'zigzag', 'star']
    
    def __init__(self, emoji_size: int = 128, canvas_size: Tuple[int, int] = (1024, 1024),
                 background_color: str = 'white', guide_line_color: str = 'darkblue',
                 agent_verbose: bool = False):
        """
        Initialize the generator
        
        Args:
            emoji_size: Size of each emoji in pixels
            canvas_size: Canvas dimensions (width, height)
            background_color: Background color
            guide_line_color: Color for guide lines (default: darkblue)
            agent_verbose: Whether to enable verbose mode for EmojiProcessAgent
        """
        self.emoji_size = emoji_size
        self.canvas_size = canvas_size
        self.background_color = background_color
        self.guide_line_color = guide_line_color
        
        # Initialize emoji processing
        self.emoji_cache = {}
        self.emoji_agent = EmojiProcessAgent(verbose=agent_verbose)
        print("EmojiProcessAgent initialized successfully")
        
        # Initialize layout engine
        self.layout_engine = LayoutEngine()
    
    
    def get_emoji_image(self, emoji: str) -> Image.Image:
        """
        Get emoji image using EmojiProcessAgent
        
        Args:
            emoji: Emoji character
            
        Returns:
            PIL Image object
        """
        # Check cache first
        if emoji in self.emoji_cache:
            return self.emoji_cache[emoji]
        
        try:
            # Create temporary file for PNG
            temp_filename = f"temp_emoji_{abs(hash(emoji))}.png"
            svg_data, source = self.emoji_agent.fetch_svg(emoji)
            
            if self.emoji_agent.convert_to_png(svg_data, self.emoji_size, temp_filename):
                emoji_img = Image.open(temp_filename)
                # Clean up temp file
                try:
                    os.remove(temp_filename)
                except:
                    pass
                
                # Cache the result
                self.emoji_cache[emoji] = emoji_img
                return emoji_img
            
        except Exception as e:
            print(f"EmojiProcessAgent failed for {emoji}: {e}")
        
        # Create placeholder if agent fails
        emoji_img = self._create_placeholder(emoji)
        self.emoji_cache[emoji] = emoji_img
        return emoji_img
    
    def _create_placeholder(self, emoji: str) -> Image.Image:
        """Create a placeholder image for emoji"""
        img = Image.new('RGBA', (self.emoji_size, self.emoji_size), (230, 230, 230, 255))
        draw = ImageDraw.Draw(img)
        
        # Draw border
        draw.rectangle([2, 2, self.emoji_size-3, self.emoji_size-3], outline='gray', width=2)
        
        # Draw emoji text in center
        try:
            font = ImageFont.load_default()
            bbox = draw.textbbox((0, 0), emoji, font=font)
            text_width = bbox[2] - bbox[0]
            text_height = bbox[3] - bbox[1]
            
            x = (self.emoji_size - text_width) // 2 - bbox[0]
            y = (self.emoji_size - text_height) // 2 - bbox[1]
            
            draw.text((x, y), emoji, fill='black', font=font)
        except:
            # If text drawing fails, just draw a simple shape
            center = self.emoji_size // 2
            draw.ellipse([center-10, center-10, center+10, center+10], fill='gray')
        
        return img
    
    def _draw_guide_elements(self, draw: ImageDraw.Draw, positions: List[Tuple[float, float]], 
                           layout_type: str, add_guide_lines: bool, add_numbers: bool) -> None:
        """Draw guide lines and numbers"""
        if add_guide_lines:
            self._draw_guide_lines_with_arrows(draw, positions, layout_type)
        
        if add_numbers:
            self._draw_numbers(draw, positions, layout_type)
    
    def _calculate_arrow_points(self, start: Tuple[float, float], end: Tuple[float, float], 
                               emoji_size: int) -> Tuple[Tuple[float, float], Tuple[float, float]]:
        """
        Calculate arrow start and end points that avoid overlapping with emojis
        
        Args:
            start: Original start position (emoji center)
            end: Original end position (emoji center) 
            emoji_size: Size of emoji
            
        Returns:
            Tuple of (adjusted_start, adjusted_end) points
        """
        # Calculate direction vector
        dx = end[0] - start[0]
        dy = end[1] - start[1]
        distance = math.sqrt(dx*dx + dy*dy)
        
        if distance == 0:
            return start, end
        
        # Normalize direction
        unit_x = dx / distance
        unit_y = dy / distance
        
        # Calculate offset distance (half emoji size plus padding)
        # Use larger offset for better visibility
        offset = emoji_size // 2 + 15  # Increased padding from 10 to 15
        
        # For very close emojis (like in vertical/horizontal layouts), ensure minimum arrow length
        min_arrow_length = 30  # Minimum visible arrow length
        if distance - 2 * offset < min_arrow_length:
            # Adjust offset to ensure minimum arrow length
            offset = max(5, (distance - min_arrow_length) // 2)
        
        # Calculate new start and end points
        new_start = (start[0] + offset * unit_x, start[1] + offset * unit_y)
        new_end = (end[0] - offset * unit_x, end[1] - offset * unit_y)
        
        return new_start, new_end
    
    def _draw_arrow(self, draw: ImageDraw.Draw, start: Tuple[float, float], end: Tuple[float, float], 
                   arrow_size: int = 16) -> None:
        """Draw an arrow from start to end point with improved size"""
        # Adjust arrow points to avoid emoji overlap
        adj_start, adj_end = self._calculate_arrow_points(start, end, self.emoji_size)
        
        # Check if there's enough distance to draw an arrow
        dx = adj_end[0] - adj_start[0]
        dy = adj_end[1] - adj_start[1]
        distance = math.sqrt(dx*dx + dy*dy)
        
        if distance < 10:  # Reduced minimum from 20 to 10 for better visibility in tight layouts
            return
        
        # Draw the main line with increased width for better visibility
        draw.line([adj_start, adj_end], fill=self.guide_line_color, width=4)  # Increased from 3 to 4
        
        # Calculate angle
        angle = math.atan2(dy, dx)
        
        # Calculate arrow head points (larger than before)
        arrow_angle = math.pi / 6  # 30 degrees
        arrow_x1 = adj_end[0] - arrow_size * math.cos(angle - arrow_angle)
        arrow_y1 = adj_end[1] - arrow_size * math.sin(angle - arrow_angle)
        arrow_x2 = adj_end[0] - arrow_size * math.cos(angle + arrow_angle)
        arrow_y2 = adj_end[1] - arrow_size * math.sin(angle + arrow_angle)
        
        # Draw arrow head
        draw.polygon([adj_end, (arrow_x1, arrow_y1), (arrow_x2, arrow_y2)], 
                    fill=self.guide_line_color, outline=self.guide_line_color)
    
    def _draw_circular_arc_with_arrow(self, draw: ImageDraw.Draw, center: Tuple[float, float], 
                                     radius: float, start_angle: float, end_angle: float, 
                                     width: int = 3) -> None:
        """Draw a circular arc between two angles with an arrow at the end"""
        # Convert to bounding box for arc
        left = center[0] - radius
        top = center[1] - radius
        right = center[0] + radius
        bottom = center[1] + radius
        
        # Convert angles to degrees
        start_deg = math.degrees(start_angle)
        end_deg = math.degrees(end_angle)
        
        # Ensure end_deg > start_deg
        if end_deg <= start_deg:
            end_deg += 360
        
        # Draw arc
        draw.arc([left, top, right, bottom], start_deg, end_deg, 
                fill=self.guide_line_color, width=width)
        
        # Add arrow at the end of the arc
        # Calculate the end point of the arc
        end_x = center[0] + radius * math.cos(end_angle)
        end_y = center[1] + radius * math.sin(end_angle)
        
        # Calculate tangent direction at end point (perpendicular to radius)
        tangent_angle = end_angle + math.pi / 2
        
        # Draw arrow head at the end
        arrow_size = 12
        arrow_angle = math.pi / 6  # 30 degrees
        
        arrow_x1 = end_x - arrow_size * math.cos(tangent_angle - arrow_angle)
        arrow_y1 = end_y - arrow_size * math.sin(tangent_angle - arrow_angle)
        arrow_x2 = end_x - arrow_size * math.cos(tangent_angle + arrow_angle)
        arrow_y2 = end_y - arrow_size * math.sin(tangent_angle + arrow_angle)
        
        # Draw arrow head
        draw.polygon([(end_x, end_y), (arrow_x1, arrow_y1), (arrow_x2, arrow_y2)], 
                    fill=self.guide_line_color, outline=self.guide_line_color)
    
    def _draw_guide_lines_with_arrows(self, draw: ImageDraw.Draw, positions: List[Tuple[float, float]], 
                                    layout_type: str) -> None:
        """Draw guide lines with arrows connecting emojis"""
        if len(positions) < 2:
            return
        
        if layout_type in ['horizontal', 'vertical', 'diagonal', 'zigzag']:
            # Connect consecutive points with arrows
            for i in range(len(positions) - 1):
                self._draw_arrow(draw, positions[i], positions[i + 1])
        
        elif layout_type == 'circular':
            # For circular layout, draw arcs with arrows connecting consecutive points
            if len(positions) >= 3:
                center_x = sum(pos[0] for pos in positions) / len(positions)
                center_y = sum(pos[1] for pos in positions) / len(positions)
                center = (center_x, center_y)
                
                # Calculate radius from center to first point
                radius = math.sqrt((positions[0][0] - center_x)**2 + (positions[0][1] - center_y)**2)
                
                # Draw arcs with arrows between consecutive points
                for i in range(len(positions)):
                    next_i = (i + 1) % len(positions)
                    
                    # Calculate angles for both points
                    angle1 = math.atan2(positions[i][1] - center_y, positions[i][0] - center_x)
                    angle2 = math.atan2(positions[next_i][1] - center_y, positions[next_i][0] - center_x)
                    
                    # Adjust for shortest arc
                    while angle2 - angle1 > math.pi:
                        angle2 -= 2 * math.pi
                    while angle1 - angle2 > math.pi:
                        angle2 += 2 * math.pi
                    
                    # Draw the arc with arrow
                    self._draw_circular_arc_with_arrow(draw, center, radius, angle1, angle2)
            else:
                # For 2 emojis, just draw an arrow
                self._draw_arrow(draw, positions[0], positions[1])
        
        elif layout_type == 'star':
            # Connect consecutive points in sequence: 1->2->3->4, not center to all
            for i in range(len(positions) - 1):
                self._draw_arrow(draw, positions[i], positions[i + 1])
        
        elif layout_type == 'grid':
            # Connect consecutive points in reading order
            for i in range(len(positions) - 1):
                self._draw_arrow(draw, positions[i], positions[i + 1])
    
    def _get_better_font(self, size: int = 20) -> ImageFont.FreeTypeFont:
        """Try to get a better font for numbers"""
        font_names = [
            # Windows fonts
            "arial.ttf", "Arial.ttf", "calibri.ttf", "Calibri.ttf",
            # Linux fonts  
            "DejaVuSans.ttf", "liberation-fonts/LiberationSans-Regular.ttf",
            "Ubuntu-R.ttf", "NotoSans-Regular.ttf",
            # macOS fonts
            "Helvetica.ttc", "Geneva.ttf"
        ]
        
        for font_name in font_names:
            try:
                return ImageFont.truetype(font_name, size)
            except:
                continue
        
        # If no TrueType font found, return default
        return ImageFont.load_default()
    
    def _draw_numbers(self, draw: ImageDraw.Draw, positions: List[Tuple[float, float]], 
                     layout_type: str = 'horizontal') -> None:
        """Draw sequence numbers at appropriate positions based on layout type"""
        font = self._get_better_font(22)
        
        # Draw numbers for exactly the same number of positions we have
        for i, (x, y) in enumerate(positions):
            number_text = str(i + 1)
            
            # Calculate text dimensions more accurately
            bbox = draw.textbbox((0, 0), number_text, font=font)
            text_width = bbox[2] - bbox[0]
            text_height = bbox[3] - bbox[1]
            
            # Position number based on layout type
            circle_size = max(32, text_width + 12, text_height + 12)
            
            if layout_type == 'vertical':
                # For vertical layout, place numbers to the right of emojis
                number_x = x + self.emoji_size // 2 + circle_size // 2 + 15  # Right side with padding
                number_y = y - circle_size // 2  # Vertically centered with emoji
            else:
                # For all other layouts, place numbers above emojis
                number_x = x - circle_size // 2
                number_y = y - self.emoji_size // 2 - circle_size - 12  # Above emoji
            
            # Enhanced boundary checking - ensure entire circle stays within canvas
            margin = 8  # Additional margin from canvas edge
            number_x = max(margin, min(number_x, self.canvas_size[0] - circle_size - margin))
            number_y = max(margin, min(number_y, self.canvas_size[1] - circle_size - margin))
            
            # Draw background circle with shadow effect
            shadow_offset = 2
            # Shadow (check bounds for shadow too)
            shadow_x = min(number_x + shadow_offset, self.canvas_size[0] - circle_size - margin)
            shadow_y = min(number_y + shadow_offset, self.canvas_size[1] - circle_size - margin)
            draw.ellipse([shadow_x, shadow_y, 
                         shadow_x + circle_size, shadow_y + circle_size], 
                        fill='rgba(0,0,0,64)')
            
            # Main circle with gradient-like effect
            draw.ellipse([number_x, number_y, number_x + circle_size, number_y + circle_size], 
                        fill='#FF4444', outline='#CC2222', width=2)
            
            # Inner highlight circle for 3D effect
            highlight_offset = 2
            highlight_size = circle_size - 4
            draw.ellipse([number_x + highlight_offset, number_y + highlight_offset, 
                         number_x + highlight_offset + highlight_size, 
                         number_y + highlight_offset + highlight_size], 
                        outline='#FF6666', width=1)
            
            # Calculate centered text position more precisely
            text_x = number_x + (circle_size - text_width) // 2 - bbox[0]
            text_y = number_y + (circle_size - text_height) // 2 - bbox[1]
            
            # Draw text shadow for better visibility
            draw.text((text_x + 1, text_y + 1), number_text, fill='#440000', font=font)
            # Draw main text
            draw.text((text_x, text_y), number_text, fill='white', font=font)
    
    def generate_single_variant(self, emoji_sequence: str, layout_type: str = 'horizontal',
                              add_guide_lines: bool = False, add_numbers: bool = False) -> Image.Image:
        """
        Generate a single layout variant
        
        Args:
            emoji_sequence: String containing emoji sequence
            layout_type: Layout type from LAYOUT_TYPES
            add_guide_lines: Whether to add guide lines
            add_numbers: Whether to add sequence numbers
            
        Returns:
            PIL Image object
        """
        # Parse emoji sequence
        emojis = self.emoji_agent.parse_emoji_sequence(emoji_sequence)
        
        if not emojis:
            raise ValueError("No valid emojis found in sequence")
        
        print(f"Parsed {len(emojis)} emojis: {emojis}")
        
        # Calculate positions
        positions = self.layout_engine.calculate_positions(
            len(emojis), layout_type, self.canvas_size, self.emoji_size
        )
        
        print(f"Generated {len(positions)} positions for layout '{layout_type}'")
        
        # Create canvas
        image = Image.new('RGB', self.canvas_size, self.background_color)
        draw = ImageDraw.Draw(image)
        
        # Draw guide elements
        self._draw_guide_elements(draw, positions, layout_type, add_guide_lines, add_numbers)
        
        # Draw emojis
        for i, (emoji, (x, y)) in enumerate(zip(emojis, positions)):
            emoji_img = self.get_emoji_image(emoji)
            
            # Calculate paste position (center the emoji)
            paste_x = int(x - self.emoji_size // 2)
            paste_y = int(y - self.emoji_size // 2)
            
            # Ensure position is within canvas bounds
            paste_x = max(0, min(paste_x, self.canvas_size[0] - self.emoji_size))
            paste_y = max(0, min(paste_y, self.canvas_size[1] - self.emoji_size))
            
            # Paste emoji
            if emoji_img.mode == 'RGBA':
                image.paste(emoji_img, (paste_x, paste_y), emoji_img)
            else:
                image.paste(emoji_img, (paste_x, paste_y))
            
            print(f"Placed emoji {i+1}: {emoji} at ({paste_x}, {paste_y})")
        
        return image
    
    def generate_variants_for_emoji_set(self, idiom: str, emoji_set: str, output_dir: str) -> Dict[str, str]:
        """
        Generate all variants for a specific emoji set according to the new structure
        
        Args:
            idiom: The idiom name
            emoji_set: String containing emoji sequence
            output_dir: Output directory for this emoji set
            
        Returns:
            Dictionary mapping variant names to file paths
        """
        # Create output directory and subdirectories
        os.makedirs(output_dir, exist_ok=True)
        pure_dir = os.path.join(output_dir, "seq_varients_pure")
        guidance_dir = os.path.join(output_dir, "seq_varients_with_guideance")
        os.makedirs(pure_dir, exist_ok=True)
        os.makedirs(guidance_dir, exist_ok=True)
        
        generated_files = {}
        variant_count = 1
        
        try:
            # 1. Generate base horizontal image (no guide, no numbers)
            print(f"    Generating base horizontal image...")
            base_image = self.generate_single_variant(emoji_set, 'horizontal', False, False)
            base_filename = f"{idiom}_base_v{variant_count:03d}.png"
            base_filepath = os.path.join(output_dir, base_filename)
            base_image.save(base_filepath)
            generated_files['base_horizontal'] = base_filepath
            print(f"    ✅ Generated base: {base_filename}")
            variant_count += 1
            
            # 2. Generate pure variants (no guide, no numbers) for other layouts
            other_layouts = ['vertical', 'diagonal', 'circular', 'grid', 'zigzag', 'star']
            for layout in other_layouts:
                try:
                    print(f"    Generating pure variant: {layout}")
                    image = self.generate_single_variant(emoji_set, layout, False, False)
                    filename = f"{idiom}_{layout}_v{variant_count:03d}.png"
                    filepath = os.path.join(pure_dir, filename)
                    image.save(filepath)
                    generated_files[f'pure_{layout}'] = filepath
                    print(f"    ✅ Generated pure: {filename}")
                    variant_count += 1
                except Exception as e:
                    print(f"    ❌ Failed to generate pure {layout}: {e}")
                    continue
            
            # 3. Generate guidance variants (3 combinations for each layout)
            # Combinations: guide_only, numbers_only, guide+numbers
            guidance_combinations = [
                ('guide_only', True, False),
                ('numbers_only', False, True),
                ('guide_and_numbers', True, True)
            ]
            
            for layout in other_layouts:
                for combo_name, guide, numbers in guidance_combinations:
                    try:
                        print(f"    Generating guidance variant: {layout}_{combo_name}")
                        image = self.generate_single_variant(emoji_set, layout, guide, numbers)
                        filename = f"{idiom}_{layout}_{combo_name}_v{variant_count:03d}.png"
                        filepath = os.path.join(guidance_dir, filename)
                        image.save(filepath)
                        generated_files[f'guidance_{layout}_{combo_name}'] = filepath
                        print(f"    ✅ Generated guidance: {filename}")
                        variant_count += 1
                    except Exception as e:
                        print(f"    ❌ Failed to generate guidance {layout}_{combo_name}: {e}")
                        continue
            
        except Exception as e:
            print(f"    ❌ Failed to generate variants: {e}")
        
        print(f"  🎉 Generated {len(generated_files)} variants for emoji set")
        return generated_files
    
    def process_idioms_from_json(self, json_path: str, output_base_dir: str) -> Dict[str, Dict[str, Dict[str, str]]]:
        """
        Process all idioms from JSON file and generate sequential variants
        
        Args:
            json_path: Path to JSON file containing idioms data
            output_base_dir: Base output directory
            
        Returns:
            Dictionary mapping idiom names to their emoji sets and generated files
        """
        # Read JSON file
        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                idioms_data = json.load(f)
            print(f"📖 Loaded {len(idioms_data)} idioms from {json_path}")
        except Exception as e:
            raise RuntimeError(f"Failed to read JSON file {json_path}: {e}")
        
        # Create base output directory
        os.makedirs(output_base_dir, exist_ok=True)
        print(f"📁 Created output directory: {output_base_dir}")
        
        all_results = {}
        successful_count = 0
        total_emoji_sets = 0
        
        # Process each idiom
        for i, item in enumerate(idioms_data):
            try:
                idiom_index = item.get("idiom_index", i+1)
                idiom = item.get("idiom", "")
                emoji_rep_list = item.get("emoji_rep", [])
                
                if not idiom or not emoji_rep_list:
                    print(f"⚠️  Skipping item {i+1}: missing idiom or emoji_rep")
                    continue
                
                print(f"\n{'='*60}")
                print(f"Processing {i+1}/{len(idioms_data)}: {idiom} (index: {idiom_index})")
                print(f"Found {len(emoji_rep_list)} emoji sets")
                
                # Create idiom directory: {idiom_index}_{idiom}
                idiom_dir_name = f"{idiom_index}_{idiom}"
                idiom_output_dir = os.path.join(output_base_dir, idiom_dir_name)
                
                idiom_results = {}
                
                # Process each emoji set in the list
                for emoji_set_data in emoji_rep_list:
                    try:
                        set_index = emoji_set_data.get("index", 1)
                        emoji_set = emoji_set_data.get("emoji_set", "")
                        homophonic_num = emoji_set_data.get("homophonic_num", 0)
                        
                        if not emoji_set:
                            print(f"  ⚠️  Skipping emoji set {set_index}: missing emoji_set")
                            continue
                        
                        print(f"  Processing emoji set {set_index}: {emoji_set} (homophonic: {homophonic_num})")
                        
                        # Create output directory for this emoji set: {index}
                        set_output_dir = os.path.join(idiom_output_dir, str(set_index))
                        
                        # Generate variants for this emoji set
                        generated_files = self.generate_variants_for_emoji_set(
                            idiom, emoji_set, set_output_dir
                        )
                        
                        idiom_results[str(set_index)] = generated_files
                        total_emoji_sets += 1
                        
                        print(f"  ✅ Completed emoji set {set_index}")
                        
                    except Exception as e:
                        print(f"  ❌ Failed to process emoji set {set_index}: {e}")
                        continue
                
                all_results[idiom] = idiom_results
                successful_count += 1
                
                print(f"✅ Completed processing: {idiom}")
                
            except Exception as e:
                print(f"❌ Failed to process idiom '{idiom}': {e}")
                continue
        
        print(f"\n{'='*60}")
        print(f"🎉 Processing complete!")
        print(f"📊 Successfully processed: {successful_count}/{len(idioms_data)} idioms")
        print(f"📊 Total emoji sets processed: {total_emoji_sets}")
        print(f"📁 Output directory: {os.path.abspath(output_base_dir)}")
        
        return all_results


def main():
    """Command line interface"""
    parser = argparse.ArgumentParser(
        description="Generate sequential emoji layout variants for idioms from JSON file",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Example usage:
  %(prog)s --datapath idioms.json --outputfolder ./output
  %(prog)s --datapath data.json --outputfolder /path/to/output
        """
    )
    
    # Input options
    parser.add_argument('--datapath', required=True, 
                       help='Path to JSON file containing idioms data')
    parser.add_argument('--outputfolder', required=True,
                       help='Output base directory')
    
    # Appearance options
    parser.add_argument('--emoji-size', type=int, default=128,
                       help='Emoji size in pixels (default: 128)')
    parser.add_argument('--canvas-size', nargs=2, type=int, default=[1024, 1024],
                       help='Canvas size in pixels (default: 1024 1024)')
    parser.add_argument('--background', default='white',
                       help='Background color (default: white)')
    parser.add_argument('--guide-color', default='darkblue',
                       help='Guide line color (default: darkblue)')
    
    # Agent options
    parser.add_argument('--verbose', '-v', action='store_true',
                       help='Enable verbose output')
    
    args = parser.parse_args()
    
    try:
        # Validate input file
        if not os.path.exists(args.datapath):
            print(f"❌ Error: JSON file not found: {args.datapath}")
            return 1
        
        # Validate output directory
        if not os.path.exists(args.outputfolder):
            try:
                os.makedirs(args.outputfolder, exist_ok=True)
                print(f"📁 Created output directory: {args.outputfolder}")
            except Exception as e:
                print(f"❌ Error: Cannot create output directory {args.outputfolder}: {e}")
                return 1
        
        # Create generator
        generator = SequentialVariantGenerator(
            emoji_size=args.emoji_size,
            canvas_size=tuple(args.canvas_size),
            background_color=args.background,
            guide_line_color=args.guide_color,
            agent_verbose=args.verbose
        )
        
        # Process all idioms from JSON
        all_results = generator.process_idioms_from_json(
            json_path=args.datapath,
            output_base_dir=args.outputfolder
        )
        
        # Summary statistics
        total_files = 0
        total_emoji_sets = 0
        for idiom_results in all_results.values():
            total_emoji_sets += len(idiom_results)
            for set_files in idiom_results.values():
                total_files += len(set_files)
        
        print(f"\n📈 Final Summary:")
        print(f"   Total idioms processed: {len(all_results)}")
        print(f"   Total emoji sets processed: {total_emoji_sets}")
        print(f"   Total files generated: {total_files}")
        if total_emoji_sets > 0:
            print(f"   Average files per emoji set: {total_files/total_emoji_sets:.1f}")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return 1
    
    return 0


if __name__ == "__main__":
    exit(main())