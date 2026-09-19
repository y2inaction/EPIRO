/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    './pages/**/*.{js,ts,jsx,tsx}',
    './components/**/*.{js,ts,jsx,tsx}',
    './app/**/*.{js,ts,jsx,tsx}',
  ],
  theme: {
    extend: {
      colors: {
        primary: '#0066cc',
        secondary: '#666666',
        success: '#28a745',
        warning: '#ffc107',
        danger: '#dc3545',
        info: '#17a2b8',

        // The data-visualisation series colour. One series, so one colour:
        // a bar's length already carries its magnitude, and shading it darker
        // where it is longer would spend the only free channel saying the
        // same thing twice.
        //
        // Both steps were checked with the dataviz palette validator against
        // the surfaces this app actually renders charts on — white in light
        // mode, slate-900 in dark — rather than picked by eye. The dark step
        // is selected for the dark surface, not derived from the light one.
        viz: {
          series: '#2a78d6',
          'series-dark': '#3987e5',
        },
      },
      fontSize: {
        xs: ['12px', '16px'],
        sm: ['14px', '20px'],
        base: ['16px', '24px'],
        lg: ['18px', '28px'],
        xl: ['20px', '28px'],
      },
    },
  },
  plugins: [],
}
