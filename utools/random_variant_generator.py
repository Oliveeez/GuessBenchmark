#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
random_variant_generator.py

Random Structure Variant Generator: Generate random layout variations 
of emoji sequences with different randomization strategies.
Integrates with EmojiProcessAgent for high-quality emoji fetching.
"""

import json
import os
import math
import random
import argparse
from typing import List, Tuple, Dict, Optional
from PIL import Image, ImageDraw, ImageFont

try:
    from emoji_process_agent import EmojiProcessAgent
except ImportError:
    raise ImportError("EmojiProcessAgent not found. Please ensure emoji_process_agent.py is in the same directory.")


class RandomLayoutEngine:
    """Random layout engine for calculating random emoji positions"""
    
    @staticmethod
    def generate_random_positions(num_emojis: int, canvas_size: Tuple[int, int], 
                                emoji_size: int, margin_ratio: float = 0.1,
                                distribution_method: str = 'uniform',
                                min_distance_ratio: float = 1.5) -> List[Tuple[float, float]]:
        """
        Generate random positions for emojis ensuring no overlap
        
        Args:
            num_emojis: Number of emojis to position
            canvas_size: Canvas dimensions (width, height)
            emoji_size: Size of each emoji
            margin_ratio: Margin as ratio of canvas size
            distribution_method: Method for distribution ('uniform', 'grid_jitter', 'poisson_disk')
            min_distance_ratio: Minimum distance between emojis as ratio of emoji_size
            
        Returns:
            List of (x, y) positions - exactly num_emojis positions
        """
        width, height = canvas_size
        margin_x = int(width * margin_ratio)
        margin_y = int(height * margin_ratio)
        available_width = width - 2 * margin_x
        available_height = height - 2 * margin_y
        min_distance = emoji_size * min_distance_ratio
        
        if distribution_method == 'uniform':
            return RandomLayoutEngine._uniform_random_positions(
                num_emojis, margin_x, margin_y, available_width, available_height, 
                emoji_size, min_distance
            )
        elif distribution_method == 'grid_jitter':
            return RandomLayoutEngine._grid_jitter_positions(
                num_emojis, margin_x, margin_y, available_width, available_height,
                emoji_size, min_distance
            )
        elif distribution_method == 'poisson_disk':
            return RandomLayoutEngine._poisson_disk_positions(
                num_emojis, margin_x, margin_y, available_width, available_height,
                emoji_size, min_distance
            )
        else:
            raise ValueError(f"Unknown distribution method: {distribution_method}")
    
    @staticmethod
    def _uniform_random_positions(num_emojis: int, margin_x: int, margin_y: int,
                                available_width: int, available_height: int,
                                emoji_size: int, min_distance: float) -> List[Tuple[float, float]]:
        """Generate completely random positions with collision avoidance"""
        positions = []
        max_attempts = 1000
        
        for i in range(num_emojis):
            attempts = 0
            while attempts < max_attempts:
                # Generate random position within available area
                x = margin_x + random.random() * (available_width - emoji_size)
                y = margin_y + random.random() * (available_height - emoji_size)
                
                # Check if position conflicts with existing positions
                valid = True
                for existing_x, existing_y in positions:
                    distance = math.sqrt((x - existing_x)**2 + (y - existing_y)**2)
                    if distance < min_distance:
                        valid = False
                        break
                
                if valid:
                    positions.append((x + emoji_size // 2, y + emoji_size // 2))  # Center position
                    break
                
                attempts += 1
            
            # If we can't find a valid position, use a fallback
            if attempts >= max_attempts:
                # Fallback: place in a spiral pattern
                angle = i * 2.3  # Golden angle approximation
                radius = 50 + i * 20
                center_x = margin_x + available_width // 2
                center_y = margin_y + available_height // 2
                
                x = center_x + radius * math.cos(angle)
                y = center_y + radius * math.sin(angle)
                
                # Clamp to bounds
                x = max(margin_x + emoji_size // 2, 
                       min(x, margin_x + available_width - emoji_size // 2))
                y = max(margin_y + emoji_size // 2,
                       min(y, margin_y + available_height - emoji_size // 2))
                
                positions.append((x, y))
        
        return positions
    
    @staticmethod
    def _grid_jitter_positions(num_emojis: int, margin_x: int, margin_y: int,
                             available_width: int, available_height: int,
                             emoji_size: int, min_distance: float) -> List[Tuple[float, float]]:
        """Generate positions on a loose grid with random jitter"""
        # Calculate grid dimensions
        cols = math.ceil(math.sqrt(num_emojis * 1.5))  # Slightly larger grid for more spacing
        rows = math.ceil(num_emojis / cols)
        
        cell_width = available_width / cols
        cell_height = available_height / rows
        
        # Maximum jitter as percentage of cell size
        max_jitter_x = cell_width * 0.3
        max_jitter_y = cell_height * 0.3
        
        positions = []
        emoji_count = 0
        
        for row in range(rows):
            for col in range(cols):
                if emoji_count >= num_emojis:
                    break
                
                # Calculate base grid position (center of cell)
                base_x = margin_x + col * cell_width + cell_width / 2
                base_y = margin_y + row * cell_height + cell_height / 2
                
                # Add random jitter
                jitter_x = (random.random() - 0.5) * 2 * max_jitter_x
                jitter_y = (random.random() - 0.5) * 2 * max_jitter_y
                
                x = base_x + jitter_x
                y = base_y + jitter_y
                
                # Ensure within bounds
                x = max(margin_x + emoji_size // 2,
                       min(x, margin_x + available_width - emoji_size // 2))
                y = max(margin_y + emoji_size // 2,
                       min(y, margin_y + available_height - emoji_size // 2))
                
                positions.append((x, y))
                emoji_count += 1
        
        return positions
    
    @staticmethod
    def _poisson_disk_positions(num_emojis: int, margin_x: int, margin_y: int,
                              available_width: int, available_height: int,
                              emoji_size: int, min_distance: float) -> List[Tuple[float, float]]:
        """Generate positions using Poisson disk sampling for even distribution"""
        # Simplified Poisson disk sampling
        positions = []
        candidates = []
        
        # Start with a random seed point
        seed_x = margin_x + available_width // 2
        seed_y = margin_y + available_height // 2
        positions.append((seed_x, seed_y))
        candidates.append((seed_x, seed_y))
        
        max_attempts_per_point = 30
        
        while len(positions) < num_emojis and candidates:
            # Pick a random candidate
            candidate_idx = random.randint(0, len(candidates) - 1)
            candidate = candidates[candidate_idx]
            
            found_valid = False
            
            # Try to generate new points around this candidate
            for attempt in range(max_attempts_per_point):
                # Generate point in annulus around candidate
                angle = random.random() * 2 * math.pi
                distance = min_distance + random.random() * min_distance
                
                x = candidate[0] + distance * math.cos(angle)
                y = candidate[1] + distance * math.sin(angle)
                
                # Check bounds
                if (x < margin_x + emoji_size // 2 or 
                    x > margin_x + available_width - emoji_size // 2 or
                    y < margin_y + emoji_size // 2 or 
                    y > margin_y + available_height - emoji_size // 2):
                    continue
                
                # Check distance to all existing points
                valid = True
                for existing_x, existing_y in positions:
                    dist = math.sqrt((x - existing_x)**2 + (y - existing_y)**2)
                    if dist < min_distance:
                        valid = False
                        break
                
                if valid:
                    positions.append((x, y))
                    candidates.append((x, y))
                    found_valid = True
                    break
            
            # If no valid point found, remove candidate
            if not found_valid:
                candidates.pop(candidate_idx)
        
        # If we don't have enough positions, fill with fallback method
        while len(positions) < num_emojis:
            positions.extend(RandomLayoutEngine._uniform_random_positions(
                num_emojis - len(positions), margin_x, margin_y,
                available_width, available_height, emoji_size, min_distance
            ))
        
        return positions[:num_emojis]


class RandomVariantGenerator:
    """Main class for generating random emoji layout variants"""
    
    # Available distribution methods for scattered layout
    DISTRIBUTION_METHODS = ['uniform', 'grid_jitter', 'poisson_disk']
    
    def __init__(self, emoji_size: int = 128, canvas_size: Tuple[int, int] = (1024, 1024),
                 background_color: str = 'white', agent_verbose: bool = False):
        """
        Initialize the random generator
        
        Args:
            emoji_size: Size of each emoji in pixels
            canvas_size: Canvas dimensions (width, height)
            background_color: Background color
            agent_verbose: Whether to enable verbose mode for EmojiProcessAgent
        """
        self.emoji_size = emoji_size
        self.canvas_size = canvas_size
        self.background_color = background_color
        
        # Initialize emoji processing
        self.emoji_cache = {}
        self.emoji_agent = EmojiProcessAgent(verbose=agent_verbose)
        print("EmojiProcessAgent initialized successfully")
        
        # Initialize layout engine
        self.layout_engine = RandomLayoutEngine()
    
    def get_emoji_image(self, emoji: str) -> Image.Image:
        """
        Get emoji image using EmojiProcessAgent (same as sequential generator)
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
        """Create a placeholder image for emoji (same as sequential generator)"""
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
    
    def generate_adjacent_swap(self, emoji_sequence: str) -> Image.Image:
        """
        Generate variant with two adjacent emojis swapped
        
        Args:
            emoji_sequence: String containing emoji sequence
            
        Returns:
            PIL Image object
        """
        # Parse emoji sequence
        emojis = self.emoji_agent.parse_emoji_sequence(emoji_sequence)
        
        if len(emojis) < 2:
            raise ValueError("Need at least 2 emojis for adjacent swap")
        
        # Make a copy and randomly swap two adjacent emojis
        swapped_emojis = emojis.copy()
        swap_index = random.randint(0, len(emojis) - 2)
        swapped_emojis[swap_index], swapped_emojis[swap_index + 1] = \
            swapped_emojis[swap_index + 1], swapped_emojis[swap_index]
        
        print(f"Adjacent swap: position {swap_index} <-> {swap_index + 1}")
        print(f"Original: {emojis}")
        print(f"Swapped:  {swapped_emojis}")
        
        # Use horizontal layout for swapped sequence
        return self._generate_layout_image(swapped_emojis, 'horizontal')
    
    def generate_full_shuffle(self, emoji_sequence: str) -> Image.Image:
        """
        Generate variant with completely shuffled emoji order
        
        Args:
            emoji_sequence: String containing emoji sequence
            
        Returns:
            PIL Image object
        """
        # Parse emoji sequence
        emojis = self.emoji_agent.parse_emoji_sequence(emoji_sequence)
        
        if not emojis:
            raise ValueError("No valid emojis found in sequence")
        
        # Shuffle the order
        shuffled_emojis = emojis.copy()
        random.shuffle(shuffled_emojis)
        
        print(f"Full shuffle:")
        print(f"Original: {emojis}")
        print(f"Shuffled: {shuffled_emojis}")
        
        # Use horizontal layout for shuffled sequence
        return self._generate_layout_image(shuffled_emojis, 'horizontal')
    
    def generate_scattered(self, emoji_sequence: str, distribution_method: str = 'uniform') -> Image.Image:
        """
        Generate variant with emojis scattered randomly in 2D space
        
        Args:
            emoji_sequence: String containing emoji sequence
            distribution_method: Distribution method ('uniform', 'grid_jitter', 'poisson_disk')
            
        Returns:
            PIL Image object
        """
        # Parse emoji sequence
        emojis = self.emoji_agent.parse_emoji_sequence(emoji_sequence)
        
        if not emojis:
            raise ValueError("No valid emojis found in sequence")
        
        if distribution_method not in self.DISTRIBUTION_METHODS:
            raise ValueError(f"Invalid distribution method: {distribution_method}. "
                           f"Valid methods: {self.DISTRIBUTION_METHODS}")
        
        # Generate random positions
        positions = self.layout_engine.generate_random_positions(
            len(emojis), self.canvas_size, self.emoji_size, 
            distribution_method=distribution_method
        )
        
        print(f"Generated scattered layout using {distribution_method} method")
        print(f"Emojis: {emojis}")
        print(f"Positions: {len(positions)} locations")
        
        # Create canvas
        image = Image.new('RGB', self.canvas_size, self.background_color)
        draw = ImageDraw.Draw(image)
        
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
    
    def _generate_layout_image(self, emojis: List[str], layout_type: str) -> Image.Image:
        """Helper method to generate image with specific layout (horizontal/vertical)"""
        # Calculate positions using simple layout
        if layout_type == 'horizontal':
            positions = self._calculate_horizontal_positions(len(emojis))
        elif layout_type == 'vertical':
            positions = self._calculate_vertical_positions(len(emojis))
        else:
            raise ValueError(f"Unsupported layout type: {layout_type}")
        
        # Create canvas
        image = Image.new('RGB', self.canvas_size, self.background_color)
        draw = ImageDraw.Draw(image)
        
        # Draw emojis
        for i, (emoji, (x, y)) in enumerate(zip(emojis, positions)):
            emoji_img = self.get_emoji_image(emoji)
            
            # Calculate paste position
            paste_x = int(x - self.emoji_size // 2)
            paste_y = int(y - self.emoji_size // 2)
            
            # Ensure bounds
            paste_x = max(0, min(paste_x, self.canvas_size[0] - self.emoji_size))
            paste_y = max(0, min(paste_y, self.canvas_size[1] - self.emoji_size))
            
            # Paste emoji
            if emoji_img.mode == 'RGBA':
                image.paste(emoji_img, (paste_x, paste_y), emoji_img)
            else:
                image.paste(emoji_img, (paste_x, paste_y))
        
        return image
    
    def _calculate_horizontal_positions(self, num_emojis: int) -> List[Tuple[float, float]]:
        """Calculate horizontal layout positions"""
        width, height = self.canvas_size
        margin_x = int(width * 0.2)
        available_width = width - 2 * margin_x
        y = height // 2
        
        positions = []
        if num_emojis == 1:
            positions.append((width // 2, y))
        else:
            for i in range(num_emojis):
                x = margin_x + (available_width * i) / (num_emojis - 1)
                positions.append((x, y))
        
        return positions
    
    def _calculate_vertical_positions(self, num_emojis: int) -> List[Tuple[float, float]]:
        """Calculate vertical layout positions"""
        width, height = self.canvas_size
        margin_y = int(height * 0.2)
        available_height = height - 2 * margin_y
        x = width // 2
        
        positions = []
        if num_emojis == 1:
            positions.append((x, height // 2))
        else:
            for i in range(num_emojis):
                y = margin_y + (available_height * i) / (num_emojis - 1)
                positions.append((x, y))
        
        return positions
    
    def generate_random_variants_for_emoji_set(self, idiom: str, emoji_set: str, 
                                             output_dir: str, rand_gen_num: int = 5) -> Dict[str, str]:
        """
        Generate all random variants for a specific emoji set according to the new structure
        
        Args:
            idiom: The idiom name
            emoji_set: String containing emoji sequence
            output_dir: Output directory for this emoji set
            rand_gen_num: Number of scattered variants to generate (default: 5)
            
        Returns:
            Dictionary mapping variant names to file paths
        """
        # Create output directory and subdirectories
        os.makedirs(output_dir, exist_ok=True)
        random_dir = os.path.join(output_dir, "random_varients")
        os.makedirs(random_dir, exist_ok=True)
        
        generated_files = {}
        variant_count = 1
        
        try:
            # 1. Generate base horizontal image (no guide, no numbers)
            print(f"    Generating base horizontal image...")
            emojis = self.emoji_agent.parse_emoji_sequence(emoji_set)
            base_image = self._generate_layout_image(emojis, 'horizontal')
            base_filename = f"{idiom}_base_v{variant_count:03d}.png"
            base_filepath = os.path.join(output_dir, base_filename)
            base_image.save(base_filepath)
            generated_files['base_horizontal'] = base_filepath
            print(f"    ✅ Generated base: {base_filename}")
            variant_count += 1
            
        except Exception as e:
            print(f"    ❌ Failed to generate base image: {e}")
        
        try:
            # 2. Adjacent swap variant
            print(f"    Generating adjacent swap variant...")
            swap_image = self.generate_adjacent_swap(emoji_set)
            swap_filename = f"{idiom}_adjacent_swap_v{variant_count:03d}.png"
            swap_path = os.path.join(random_dir, swap_filename)
            swap_image.save(swap_path)
            generated_files["adjacent_swap"] = swap_path
            print(f"    ✅ Generated: {swap_filename}")
            variant_count += 1
            
        except Exception as e:
            print(f"    ❌ Failed to generate adjacent swap: {e}")
        
        try:
            # 3. Full shuffle variant
            print(f"    Generating full shuffle variant...")
            shuffle_image = self.generate_full_shuffle(emoji_set)
            shuffle_filename = f"{idiom}_full_shuffle_v{variant_count:03d}.png"
            shuffle_path = os.path.join(random_dir, shuffle_filename)
            shuffle_image.save(shuffle_path)
            generated_files["full_shuffle"] = shuffle_path
            print(f"    ✅ Generated: {shuffle_filename}")
            variant_count += 1
            
        except Exception as e:
            print(f"    ❌ Failed to generate full shuffle: {e}")
        
        # 4. Scattered variants (5 total: cycle through distribution methods)
        print(f"    Generating {rand_gen_num} scattered variants...")
        for i in range(rand_gen_num):
            try:
                # Cycle through different distribution methods
                method = self.DISTRIBUTION_METHODS[i % len(self.DISTRIBUTION_METHODS)]
                
                scattered_image = self.generate_scattered(emoji_set, method)
                scattered_filename = f"{idiom}_scattered_{method}_v{variant_count:03d}.png"
                scattered_path = os.path.join(random_dir, scattered_filename)
                scattered_image.save(scattered_path)
                generated_files[f"scattered_{method}_{i+1}"] = scattered_path
                print(f"    ✅ Generated: {scattered_filename}")
                variant_count += 1
                
            except Exception as e:
                print(f"    ❌ Failed to generate scattered variant {i+1}: {e}")
        
        print(f"  🎉 Generated {len(generated_files)} variants for emoji set")
        return generated_files
    
    def process_idioms_from_json(self, json_path: str, output_base_dir: str, 
                                rand_gen_num: int = 5) -> Dict[str, Dict[str, Dict[str, str]]]:
        """
        Process all idioms from JSON file and generate random variants
        
        Args:
            json_path: Path to JSON file containing idioms data
            output_base_dir: Base output directory
            rand_gen_num: Number of scattered variants to generate for each emoji set
            
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
                        generated_files = self.generate_random_variants_for_emoji_set(
                            idiom, emoji_set, set_output_dir, rand_gen_num
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
        description="Generate random emoji layout variants for idioms from JSON file",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Example usage:
  %(prog)s --datapath idioms.json --outputfolder ./output
  %(prog)s --datapath data.json --outputfolder /path/to/output --rand-gen-num 3
        """
    )
    
    # Input options
    parser.add_argument('--datapath', required=True, 
                       help='Path to JSON file containing idioms data')
    parser.add_argument('--outputfolder', required=True,
                       help='Output base directory')
    
    # Random generation options
    parser.add_argument('--rand-gen-num', type=int, default=5,
                       help='Number of scattered variants to generate per emoji set (default: 5)')
    
    # Appearance options
    parser.add_argument('--emoji-size', type=int, default=128,
                       help='Emoji size in pixels (default: 128)')
    parser.add_argument('--canvas-size', nargs=2, type=int, default=[1024, 1024],
                       help='Canvas size in pixels (default: 1024 1024)')
    parser.add_argument('--background', default='white',
                       help='Background color (default: white)')
    
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
        
        # Set random seed for reproducibility if needed
        # random.seed(42)  # Uncomment for reproducible results
        
        # Create generator
        generator = RandomVariantGenerator(
            emoji_size=args.emoji_size,
            canvas_size=tuple(args.canvas_size),
            background_color=args.background,
            agent_verbose=args.verbose
        )
        
        # Process all idioms from JSON
        all_results = generator.process_idioms_from_json(
            json_path=args.datapath,
            output_base_dir=args.outputfolder,
            rand_gen_num=args.rand_gen_num
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