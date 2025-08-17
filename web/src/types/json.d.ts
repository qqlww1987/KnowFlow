// Ambient module declarations for JSON and @parent alias
// This allows importing JSON files and modules via the @parent alias without TS errors

declare module '*.json' {
  const value: any;
  export default value;
}

declare module '@parent/*' {
  const value: any;
  export default value;
}
