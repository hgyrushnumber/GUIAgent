"""
Accessibility Tree Preprocessor

Preprocesses raw XML accessibility tree into structured JSON components
before sending to the LLM. Extracts actionable UI components with their
properties (role, visibility, actions, geometry).
"""

import xml.etree.ElementTree as ET
import re
from typing import Dict, Any, List, Optional, Tuple
from pcguiagent.utils.logger import get_logger

logger = get_logger("A11yPreprocessor")


class A11yTreePreprocessor:
    """
    Preprocesses accessibility tree XML into structured components.
    """
    
    # Layout-only roles to exclude from actionable components
    LAYOUT_ONLY_ROLES = {
        "panel", "filler", "frame", "container", "separator", 
        "spacer", "layered-pane", "scroll-pane", "split-pane",
        "desktop-frame", "desktop", "unknown"
    }
    
    # Namespace mappings for Ubuntu and Windows
    NAMESPACES = {
        "ubuntu": {
            "st": "https://accessibility.ubuntu.example.org/ns/state",
            "attr": "https://accessibility.ubuntu.example.org/ns/attributes",
            "cp": "https://accessibility.ubuntu.example.org/ns/component",
            "act": "https://accessibility.ubuntu.example.org/ns/action",
            "val": "https://accessibility.ubuntu.example.org/ns/value",
        },
        "windows": {
            "st": "https://accessibility.windows.example.org/ns/state",
            "attr": "https://accessibility.windows.example.org/ns/attributes",
            "cp": "https://accessibility.windows.example.org/ns/component",
            "act": "https://accessibility.windows.example.org/ns/action",
            "val": "https://accessibility.windows.example.org/ns/value",
            "class": "https://accessibility.windows.example.org/ns/class",
        }
    }
    
    def __init__(self):
        """Initialize the preprocessor."""
        self._platform: Optional[str] = None
        self._namespaces: Optional[Dict[str, str]] = None
    
    def preprocess(
        self, 
        a11y_tree: str, 
        platform: str = "ubuntu"
    ) -> List[Dict[str, Any]]:
        """
        Preprocess accessibility tree XML into structured components.
        
        Args:
            a11y_tree: Raw XML accessibility tree string
            platform: Platform type ("ubuntu" or "windows")
        
        Returns:
            List of structured component dictionaries
        """
        if not a11y_tree or not a11y_tree.strip():
            logger.warning("[A11yPreprocessor] Empty accessibility tree provided")
            return []
        
        self._platform = platform
        self._namespaces = self.NAMESPACES.get(platform, self.NAMESPACES["ubuntu"])
        
        try:
            # Parse XML
            root = ET.fromstring(a11y_tree)
            
            # Auto-detect platform from namespaces if not specified
            if not self._detect_platform(root):
                logger.warning(f"[A11yPreprocessor] Could not detect platform, using {platform}")
            
            # Extract all components
            components = []
            self._extract_components(root, components)
            
            # Filter actionable components
            actionable = self._filter_actionable(components)
            
            logger.info(
                f"[A11yPreprocessor] Extracted {len(components)} components, "
                f"{len(actionable)} actionable"
            )
            
            # Rank components by relevance
            ranked = self._rank_components(actionable)
            
            return ranked
            
        except ET.ParseError as e:
            logger.error(f"[A11yPreprocessor] Failed to parse XML: {e}")
            return []
        except Exception as e:
            logger.error(f"[A11yPreprocessor] Unexpected error: {e}", exc_info=True)
            return []
    
    def _detect_platform(self, root: ET.Element) -> bool:
        """
        Detect platform from XML root element namespaces.
        
        Args:
            root: XML root element
        
        Returns:
            True if platform detected, False otherwise
        """
        # Check namespace map in root (lxml ElementTree)
        if hasattr(root, 'nsmap') and root.nsmap:
            for ns_url in root.nsmap.values():
                if "ubuntu" in ns_url:
                    self._platform = "ubuntu"
                    self._namespaces = self.NAMESPACES["ubuntu"]
                    return True
                elif "windows" in ns_url:
                    self._platform = "windows"
                    self._namespaces = self.NAMESPACES["windows"]
                    return True
        
        # Check attributes for namespace hints (works with standard ElementTree)
        for key in root.attrib.keys():
            if "ubuntu" in key.lower():
                self._platform = "ubuntu"
                self._namespaces = self.NAMESPACES["ubuntu"]
                return True
            elif "windows" in key.lower():
                self._platform = "windows"
                self._namespaces = self.NAMESPACES["windows"]
                return True
        
        # Check tag namespace (standard ElementTree format: {namespace}tag)
        if "}" in root.tag:
            ns_url = root.tag.split("}")[0][1:]  # Remove leading {
            if "ubuntu" in ns_url:
                self._platform = "ubuntu"
                self._namespaces = self.NAMESPACES["ubuntu"]
                return True
            elif "windows" in ns_url:
                self._platform = "windows"
                self._namespaces = self.NAMESPACES["windows"]
                return True
        
        return False
    
    def _extract_components(
        self, 
        node: ET.Element, 
        components: List[Dict[str, Any]]
    ) -> None:
        """
        Recursively extract components from XML tree.
        
        Args:
            node: Current XML element
            components: List to append extracted components to
        """
        # Extract component properties
        component = self._extract_component_properties(node)
        
        if component:
            components.append(component)
        
        # Recursively process children
        for child in node:
            self._extract_components(child, components)
    
    def _extract_component_properties(self, node: ET.Element) -> Optional[Dict[str, Any]]:
        """
        Extract properties from a single XML node.
        
        Args:
            node: XML element
        
        Returns:
            Component dictionary or None if invalid
        """
        attrs = node.attrib
        
        # Extract role (XML tag name) - handle namespaced tags like "{namespace}tag-name"
        if "}" in node.tag:
            role = node.tag.split("}")[-1]
        else:
            role = node.tag
        
        # Extract basic attributes
        name = attrs.get("name", "")
        text = (node.text or "").strip()
        
        # Extract visibility from state namespace
        visibility = self._extract_visibility(attrs)
        
        # Extract supported actions from action namespace
        supported_actions = self._extract_supported_actions(attrs)
        
        # Extract geometry
        geometry = self._extract_geometry(attrs)
        
        # Extract class and description from attributes namespace
        component_class = self._get_namespaced_attr(attrs, "attr", "class")
        description = self._get_namespaced_attr(attrs, "attr", "description")
        
        # Extract additional attributes
        value = self._get_namespaced_attr(attrs, "val", "value") or attrs.get("value", "")
        label = attrs.get("label", "") or attrs.get("aria-label", "")
        
        # Extract state information
        state_info = {}
        checked = self._get_namespaced_attr(attrs, "st", "checked")
        if checked is not None:
            state_info["checked"] = self._parse_bool(checked, False)
        selected = self._get_namespaced_attr(attrs, "st", "selected")
        if selected is not None:
            state_info["selected"] = self._parse_bool(selected, False)
        expanded = self._get_namespaced_attr(attrs, "st", "expanded")
        if expanded is not None:
            state_info["expanded"] = self._parse_bool(expanded, False)
        
        # Determine if actionable (strict criteria)
        actionable = (
            len(supported_actions) > 0 and
            visibility.get("visible", False) and
            visibility.get("enabled", False) and
            role.lower() not in self.LAYOUT_ONLY_ROLES
        )
        
        return {
            "role": role,
            "name": name,
            "text": text,
            "visibility": visibility,
            "actionable": actionable,
            "supported_actions": supported_actions,
            "geometry": geometry,
            "class": component_class or "",
            "description": description or "",
            "value": value,
            "label": label,
            "state": state_info if state_info else None,
        }
    
    def _extract_visibility(self, attrs: Dict[str, str]) -> Dict[str, bool]:
        """
        Extract visibility properties from state namespace.
        
        Args:
            attrs: Element attributes
        
        Returns:
            Dictionary with visible, showing, enabled flags
        """
        visibility = {
            "visible": False,
            "showing": False,
            "enabled": False,
        }
        
        # Check state namespace attributes
        visible_val = self._get_namespaced_attr(attrs, "st", "visible")
        showing_val = self._get_namespaced_attr(attrs, "st", "showing")
        enabled_val = self._get_namespaced_attr(attrs, "st", "enabled")
        
        # Parse boolean values
        visibility["visible"] = self._parse_bool(visible_val, default=False)
        visibility["showing"] = self._parse_bool(showing_val, default=False)
        visibility["enabled"] = self._parse_bool(enabled_val, default=True)  # Default enabled
        
        return visibility
    
    def _extract_supported_actions(self, attrs: Dict[str, str]) -> List[str]:
        """
        Extract supported actions from action namespace (act:* attributes).
        
        Args:
            attrs: Element attributes
        
        Returns:
            List of action names (e.g., ["click", "press", "activate"])
        """
        actions = []
        act_ns = self._namespaces.get("act", "")
        
        if not act_ns:
            return actions
        
        # Look for act:* attributes
        act_prefix = f"{{{act_ns}}}"
        
        for key, value in attrs.items():
            if key.startswith(act_prefix):
                # Extract action name (e.g., "{ns}click_desc" -> "click")
                action_name = key[len(act_prefix):]
                # Remove suffixes like "_desc", "_kb"
                action_name = re.sub(r"_(desc|kb|key)$", "", action_name)
                
                if action_name and action_name not in actions:
                    actions.append(action_name)
        
        return sorted(actions)
    
    def _extract_geometry(self, attrs: Dict[str, str]) -> Optional[Dict[str, Any]]:
        """
        Extract geometry information (bbox, center, area) from component namespace.
        Supports multiple coordinate formats for better coverage.
        
        Args:
            attrs: Element attributes
        
        Returns:
            Geometry dictionary or None if coordinates unavailable
        """
        # Method 1: Try component namespace (screencoord + size)
        screencoord_str = self._get_namespaced_attr(attrs, "cp", "screencoord")
        size_str = self._get_namespaced_attr(attrs, "cp", "size")
        
        if screencoord_str and size_str:
            x, y = self._parse_coordinates(screencoord_str)
            width, height = self._parse_size(size_str)
            
            if x is not None and y is not None and width is not None and height is not None:
                if width > 0 and height > 0:
                    return self._build_geometry_dict(x, y, width, height)
        
        # Method 2: Try bounds attribute (format: "x1,y1 x2,y2" or "left,top,right,bottom")
        bounds_str = attrs.get("bounds") or attrs.get("boundingBox")
        if bounds_str:
            geometry = self._parse_bounds(bounds_str)
            if geometry:
                return geometry
        
        # Method 3: Try separate x, y, width, height attributes
        x_attr = attrs.get("x") or attrs.get("left")
        y_attr = attrs.get("y") or attrs.get("top")
        width_attr = attrs.get("width") or attrs.get("w")
        height_attr = attrs.get("height") or attrs.get("h")
        
        if x_attr and y_attr and width_attr and height_attr:
            try:
                x = int(float(x_attr))
                y = int(float(y_attr))
                width = int(float(width_attr))
                height = int(float(height_attr))
                
                if width > 0 and height > 0:
                    return self._build_geometry_dict(x, y, width, height)
            except (ValueError, TypeError):
                pass
        
        # Method 4: Try position attribute
        position_str = attrs.get("position")
        if position_str:
            pos_match = re.match(r"\(?\s*(\d+)\s*[,;\s]\s*(\d+)\s*\)?", position_str.strip())
            if pos_match:
                try:
                    x = int(pos_match.group(1))
                    y = int(pos_match.group(2))
                    # Try to get size from other attributes
                    width_attr = attrs.get("width") or attrs.get("w") or "100"  # Default size
                    height_attr = attrs.get("height") or attrs.get("h") or "30"
                    width = int(float(width_attr))
                    height = int(float(height_attr))
                    
                    if width > 0 and height > 0:
                        return self._build_geometry_dict(x, y, width, height)
                except (ValueError, TypeError):
                    pass
        
        return None
    
    def _parse_coordinates(self, coord_str: str) -> Tuple[Optional[int], Optional[int]]:
        """
        Parse coordinate string to (x, y).
        
        Args:
            coord_str: Coordinate string in various formats
        
        Returns:
            (x, y) tuple or (None, None) if parsing fails
        """
        if not coord_str:
            return None, None
        
        # Try format: "(x, y)" or "x, y" or "x y"
        coord_match = re.match(r"\(?\s*(\d+)\s*[,;\s]\s*(\d+)\s*\)?", coord_str.strip())
        if coord_match:
            try:
                x = int(coord_match.group(1))
                y = int(coord_match.group(2))
                return x, y
            except (ValueError, IndexError):
                pass
        
        return None, None
    
    def _parse_size(self, size_str: str) -> Tuple[Optional[int], Optional[int]]:
        """
        Parse size string to (width, height).
        
        Args:
            size_str: Size string in various formats
        
        Returns:
            (width, height) tuple or (None, None) if parsing fails
        """
        if not size_str:
            return None, None
        
        # Try format: "(width, height)" or "width, height" or "width height"
        size_match = re.match(r"\(?\s*(\d+)\s*[,;\s]\s*(\d+)\s*\)?", size_str.strip())
        if size_match:
            try:
                width = int(size_match.group(1))
                height = int(size_match.group(2))
                return width, height
            except (ValueError, IndexError):
                pass
        
        return None, None
    
    def _parse_bounds(self, bounds_str: str) -> Optional[Dict[str, Any]]:
        """
        Parse bounds attribute to geometry.
        
        Supports formats:
        - "x1,y1 x2,y2"
        - "left,top,right,bottom"
        
        Args:
            bounds_str: Bounds string
        
        Returns:
            Geometry dictionary or None
        """
        if not bounds_str:
            return None
        
        bounds_str = bounds_str.strip()
        
        # Try format: "x1,y1 x2,y2"
        match1 = re.match(r"(\d+),(\d+)\s+(\d+),(\d+)", bounds_str)
        if match1:
            try:
                x1, y1 = int(match1.group(1)), int(match1.group(2))
                x2, y2 = int(match1.group(3)), int(match1.group(4))
                x = min(x1, x2)
                y = min(y1, y2)
                width = abs(x2 - x1)
                height = abs(y2 - y1)
                
                if width > 0 and height > 0:
                    return self._build_geometry_dict(x, y, width, height)
            except (ValueError, IndexError):
                pass
        
        # Try format: "left,top,right,bottom"
        match2 = re.match(r"(\d+),(\d+),(\d+),(\d+)", bounds_str)
        if match2:
            try:
                left = int(match2.group(1))
                top = int(match2.group(2))
                right = int(match2.group(3))
                bottom = int(match2.group(4))
                x = left
                y = top
                width = right - left
                height = bottom - top
                
                if width > 0 and height > 0:
                    return self._build_geometry_dict(x, y, width, height)
            except (ValueError, IndexError):
                pass
        
        return None
    
    def _build_geometry_dict(self, x: int, y: int, width: int, height: int) -> Dict[str, Any]:
        """
        Build geometry dictionary from coordinates and dimensions.
        
        Args:
            x: X coordinate
            y: Y coordinate
            width: Width
            height: Height
        
        Returns:
            Geometry dictionary
        """
        center_x = x + width // 2
        center_y = y + height // 2
        area = width * height
        
        return {
            "bbox": {
                "x": x,
                "y": y,
                "width": width,
                "height": height,
            },
            "center": {
                "x": center_x,
                "y": center_y,
            },
            "area": area,
        }
    
    def _get_namespaced_attr(
        self, 
        attrs: Dict[str, str], 
        ns_prefix: str, 
        attr_name: str
    ) -> Optional[str]:
        """
        Get attribute value from namespaced attribute.
        
        Args:
            attrs: Element attributes dictionary
            ns_prefix: Namespace prefix (e.g., "st", "attr", "cp", "act")
            attr_name: Attribute name (e.g., "visible", "class")
        
        Returns:
            Attribute value or None if not found
        """
        ns_url = self._namespaces.get(ns_prefix)
        if not ns_url:
            return None
        
        # Try full namespace format: {namespace_url}attr_name
        full_key = f"{{{ns_url}}}{attr_name}"
        if full_key in attrs:
            return attrs[full_key]
        
        # Try alternative formats
        # Some XML parsers may use different formats
        for key, value in attrs.items():
            if attr_name in key and ns_url in key:
                return value
        
        return None
    
    def _parse_bool(self, value: Optional[str], default: bool = False) -> bool:
        """
        Parse boolean value from string.
        
        Args:
            value: String value to parse
            default: Default value if parsing fails
        
        Returns:
            Boolean value
        """
        if value is None:
            return default
        
        value_lower = value.lower().strip()
        if value_lower in ("true", "1", "yes", "on"):
            return True
        elif value_lower in ("false", "0", "no", "off"):
            return False
        
        return default
    
    def _filter_actionable(
        self, 
        components: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Filter components with relaxed criteria (two-tier filtering).
        
        Tier 1 (Primary): Fully actionable components (has act:* AND visible AND enabled)
        Tier 2 (Secondary): Components with geometry AND visible (even without act:*)
        
        Args:
            components: List of all components
        
        Returns:
            Filtered list with primary components first, then secondary
        """
        primary = []  # Fully actionable
        secondary = []  # Has geometry but no act:*
        
        for component in components:
            has_actions = len(component.get("supported_actions", [])) > 0
            is_visible = component.get("visibility", {}).get("visible", False)
            is_enabled = component.get("visibility", {}).get("enabled", False)
            has_geometry = component.get("geometry") is not None
            role = component.get("role", "").lower()
            is_layout_only = role in self.LAYOUT_ONLY_ROLES
            
            # Skip layout-only components
            if is_layout_only:
                continue
            
            # Tier 1: Fully actionable (has act:* AND visible AND enabled)
            if has_actions and is_visible and is_enabled:
                primary.append(component)
            # Tier 2: Has geometry and visible (useful for navigation/clicking)
            elif has_geometry and is_visible:
                # Mark as not fully actionable but still useful
                component_copy = component.copy()
                component_copy["actionable"] = False
                secondary.append(component_copy)
        
        # Combine: primary first, then secondary
        result = primary + secondary
        logger.info(
            f"[A11yPreprocessor._filter_actionable] Filtered to {len(primary)} primary + "
            f"{len(secondary)} secondary = {len(result)} total components"
        )
        return result
    
    def _rank_components(self, components: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Rank components by relevance for agent decision-making.
        
        Components are scored based on:
        - Role priority (interactive roles score higher)
        - Has descriptive information (name/text)
        - Size (larger components are more likely to be clickable)
        - Actionable status (actionable components score higher)
        
        Args:
            components: List of component dictionaries
        
        Returns:
            Ranked list of components (most relevant first)
        """
        def score_component(comp: Dict[str, Any]) -> float:
            score = 0.0
            
            # Role priority - interactive roles score higher
            role = comp.get("role", "").lower()
            role_scores = {
                "push-button": 15,
                "text-field": 15,
                "combo-box": 15,
                "check-box": 12,
                "radio-button": 12,
                "menu-item": 12,
                "icon": 8,
                "label": 6,
                "text": 5,
                "link": 10,
                "table-cell": 8,
            }
            score += role_scores.get(role, 3)
            
            # Has descriptive info (name or text) - more descriptive = better
            has_name = bool(comp.get("name", "").strip())
            has_text = bool(comp.get("text", "").strip())
            if has_name:
                score += 8  # Name is more important
            elif has_text:
                score += 5  # Text is also useful
            
            # Size (larger = more likely to be clickable, but not too large)
            geometry = comp.get("geometry")
            if geometry:
                area = geometry.get("area", 0)
                # Prefer medium-sized components (not too small, not too large)
                # Optimal range: 500-5000 pixels
                if 500 <= area <= 5000:
                    score += 8
                elif 100 <= area < 500 or 5000 < area <= 20000:
                    score += 5
                elif area >= 100:
                    score += 2
                
                # Bonus for reasonable dimensions (not too thin or too wide)
                bbox = geometry.get("bbox", {})
                width = bbox.get("width", 0)
                height = bbox.get("height", 0)
                if width > 0 and height > 0:
                    aspect_ratio = max(width, height) / min(width, height) if min(width, height) > 0 else 1
                    if 1 <= aspect_ratio <= 5:  # Reasonable aspect ratio
                        score += 2
            
            # Actionable bonus
            if comp.get("actionable"):
                score += 12
            
            # Has supported actions
            supported_actions = comp.get("supported_actions", [])
            if supported_actions:
                score += len(supported_actions) * 2
            
            # Visibility and enabled status
            visibility = comp.get("visibility", {})
            if visibility.get("visible") and visibility.get("enabled"):
                score += 5
            elif visibility.get("visible"):
                score += 2
            
            return score
        
        # Score and sort components
        scored_components = [(comp, score_component(comp)) for comp in components]
        scored_components.sort(key=lambda x: x[1], reverse=True)
        
        ranked = [comp for comp, score in scored_components]
        
        logger.debug(
            f"[A11yPreprocessor._rank_components] Ranked {len(ranked)} components. "
            f"Top 5 scores: {[score_component(comp) for comp in ranked[:5]]}"
        )
        
        return ranked

