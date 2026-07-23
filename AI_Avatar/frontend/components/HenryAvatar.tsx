import React from "react";

export interface HenryAvatarProps { src: string; alt?: string; }

export function HenryAvatar({ src, alt = "Henry AI Avatar" }: HenryAvatarProps) {
  return <div className="henry-avatar"><img src={src} alt={alt} draggable={false} /></div>;
}
