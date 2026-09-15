// SVGO 4 configuration for traced assets. Keeps viewBox (responsive scaling), converts
// width/height into it, and trims numeric precision to a level the QA diff cannot see.
export default {
  multipass: true,
  floatPrecision: 2,
  plugins: [
    {
      name: "preset-default",
      params: {
        overrides: {
          // Merging paths across colours breaks the per-region layering vtracer produced.
          mergePaths: false,
        },
      },
    },
    "removeDimensions",
    { name: "removeAttrs", params: { attrs: ["data-name", "class"] } },
  ],
};
